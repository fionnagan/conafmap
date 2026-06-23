#!/usr/bin/env python3
"""embed_chunks.py — embed both text variants into committed int8 matrices.

Builds TWO embedding matrices over data/rag/chunks_contextual.jsonl so the smoke
eval (X1) can A/B them:
  - contextual : embeddings of contextual_text (LLM blurb + chunk)
  - metadata   : embeddings of metadata_text   (frontmatter + chunk)  [free baseline]

Vectors are L2-normalized to unit length (query-time cosine == dot product) and
stored int8 (component = round(v * 127)) so the committed matrix is ~8MB. The
request path dequantizes once on cold start.

Provider: Voyage voyage-3 (1024-dim) via REST + urllib (no SDK dependency). Free
under Voyage's 200M-token tier.

Free-tier note: without a payment method Voyage caps at 3 RPM / 10K TPM. Use
--throttle to stay under that (token-budgeted batches paced at 3 req/min). The run
is RESUMABLE: each embedding is appended to data/rag/_emb_cache.jsonl, so a killed
run continues where it left off. The npz/meta are assembled only once all
2 x N embeddings are cached.

Auth: VOYAGE_API_KEY from env or .env.local (never printed/stored).

Outputs:
  data/rag/embeddings.npz   — ctx_int8, meta_int8 (N x 1024 int8), chunk_ids, dim, scale
  data/rag/chunks_meta.json — {corpus_hash, model, dim, count, rows:[per-chunk metadata]}
"""
import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.error

import numpy as np

IN_FILE = "data/rag/chunks_contextual.jsonl"
CACHE = "data/rag/_emb_cache.jsonl"
NPZ_OUT = "data/rag/embeddings.npz"
META_OUT = "data/rag/chunks_meta.json"

MODEL = "voyage-3"
DIM = 1024
SCALE = 127.0
API_URL = "https://api.voyageai.com/v1/embeddings"

# Fast (paid) defaults; --throttle switches to free-tier-safe values.
BATCH_FAST = 100
TOKEN_BUDGET = 8000     # stay under the 10K TPM free cap per request
PACE_SEC = 21           # 3 RPM -> one request per 20s (+margin)

META_FIELDS = ["chunk_id", "episode_slug", "episode_title", "fan_name",
               "fan_location", "fan_occupation", "date", "source",
               "ts_start", "segment_ts", "speakers", "word_count", "text", "blurb"]


def load_env_local():
    if not os.path.exists(".env.local"):
        return
    for line in open(".env.local", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def est_tokens(s):
    return max(1, len(s) // 4)


def embed_batch(texts, api_key, max_other=6):
    """429 (rate limit) is retried indefinitely with capped backoff so a free-tier
    run can never crash on rate limits — it only slows down. Other transient
    errors get a bounded number of retries."""
    payload = json.dumps({"input": texts, "model": MODEL,
                          "input_type": "document"}).encode("utf-8")
    other = 0
    backoff = PACE_SEC
    while True:
        try:
            req = urllib.request.Request(
                API_URL, data=payload,
                headers={"Authorization": "Bearer " + api_key,
                         "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            items = sorted(data["data"], key=lambda d: d["index"])
            return [it["embedding"] for it in items]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  HTTP 429, waiting {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)   # capped exponential, never give up
                continue
            if e.code in (500, 502, 503, 529) and other < max_other:
                other += 1
                time.sleep(2 ** other)
                continue
            raise
        except urllib.error.URLError:
            if other < max_other:
                other += 1
                time.sleep(2 ** other)
                continue
            raise


def make_batches(items, throttle):
    """items: list of (key, text). Yield batches under the token/size budget."""
    if not throttle:
        for i in range(0, len(items), BATCH_FAST):
            yield items[i:i + BATCH_FAST]
        return
    cur, cur_tok = [], 0
    for key, text in items:
        t = est_tokens(text)
        if cur and (cur_tok + t > TOKEN_BUDGET or len(cur) >= 60):
            yield cur
            cur, cur_tok = [], 0
        cur.append((key, text))
        cur_tok += t
    if cur:
        yield cur


def load_cache():
    done = {}
    if os.path.exists(CACHE):
        for line in open(CACHE, encoding="utf-8"):
            r = json.loads(line)
            done[r["k"]] = r["v"]
    return done


def run_embeddings(rows, api_key, throttle):
    """Fill the cache with every (variant, chunk_id) embedding. Resumable."""
    done = load_cache()
    work = []
    for r in rows:
        for variant, field in (("ctx", "contextual_text"), ("meta", "metadata_text")):
            k = f"{variant}|{r['chunk_id']}"
            if k not in done:
                work.append((k, r[field]))
    if not work:
        print("all embeddings already cached")
        return done
    print(f"{len(work)} embeddings to fetch ({'throttled 3RPM' if throttle else 'fast'})")
    cache_f = open(CACHE, "a", encoding="utf-8")
    n = 0
    for batch in make_batches(work, throttle):
        keys = [k for k, _ in batch]
        vecs = embed_batch([t for _, t in batch], api_key)
        for k, v in zip(keys, vecs):
            cache_f.write(json.dumps({"k": k, "v": v}) + "\n")
            done[k] = v
        cache_f.flush()
        n += len(batch)
        print(f"  {n}/{len(work)} embedded")
        if throttle:
            time.sleep(PACE_SEC)
    cache_f.close()
    return done


def to_unit_int8(arr):
    arr = np.asarray(arr, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = arr / norms
    q = np.clip(np.round(unit * SCALE), -127, 127).astype(np.int8)
    err = float(np.max(np.abs(q.astype(np.float32) / SCALE - unit)))
    return q, unit, err


def corpus_hash(rows):
    h = hashlib.sha256()
    for r in rows:
        h.update(r["chunk_id"].encode("utf-8"))
        h.update(r["text"].encode("utf-8"))
    return h.hexdigest()[:16]


def assemble(rows, done):
    ctx = [done[f"ctx|{r['chunk_id']}"] for r in rows]
    meta = [done[f"meta|{r['chunk_id']}"] for r in rows]
    ctx_q, ctx_unit, ctx_err = to_unit_int8(ctx)
    meta_q, _, meta_err = to_unit_int8(meta)
    assert ctx_q.shape == (len(rows), DIM), f"bad ctx shape {ctx_q.shape}"
    assert meta_q.shape == (len(rows), DIM), f"bad meta shape {meta_q.shape}"

    # int8 cosine preservation sanity (vs vector 0)
    d = ctx_q.astype(np.float32) / SCALE
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    cos_err = float(np.max(np.abs((ctx_unit @ ctx_unit[0]) - (d @ d[0]))))

    chash = corpus_hash(rows)
    np.savez_compressed(NPZ_OUT, ctx_int8=ctx_q, meta_int8=meta_q,
                        chunk_ids=np.array([r["chunk_id"] for r in rows]),
                        dim=DIM, scale=SCALE)
    json.dump({"corpus_hash": chash, "model": MODEL, "dim": DIM, "count": len(rows),
               "rows": [{k: r.get(k) for k in META_FIELDS} for r in rows]},
              open(META_OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nint8 round-trip max abs error: ctx={ctx_err:.4f} meta={meta_err:.4f}")
    print(f"int8 cosine-preservation max error: {cos_err:.5f}")
    print(f"wrote {NPZ_OUT} ({os.path.getsize(NPZ_OUT)/1e6:.1f} MB) and {META_OUT}")
    print(f"corpus_hash={chash} rows={len(rows)}")


def main():
    load_env_local()
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        sys.exit("ERROR: VOYAGE_API_KEY not set (env or .env.local).")
    throttle = "--throttle" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0

    rows = [json.loads(l) for l in open(IN_FILE, encoding="utf-8")]
    if limit:
        rows = rows[:limit]
    print(f"embedding {len(rows)} chunks x 2 variants ({MODEL}, {DIM}d)")
    done = run_embeddings(rows, api_key, throttle)
    assemble(rows, done)


if __name__ == "__main__":
    main()
