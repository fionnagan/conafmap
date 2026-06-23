"""api/retrieval.py — hybrid (vector + BM25) retrieval over the committed corpus.

Loaded lazily and held module-global so warm invocations reuse the dequantized
matrix + BM25 index (A3). No vector DB: cosine over ~3.3k unit vectors plus a
pure-Python BM25 pass is single-digit ms.

Pipeline (called by api/ask.py on a cache miss):
  embed query (Voyage voyage-3, fail-open) -> vector cosine top-N
  + tokenize query -> contextual BM25 top-N
  -> fuse via reciprocal rank fusion (RRF) -> top-K chunks.

Why hybrid: vectors occasionally miss exact-term / proper-noun queries
catastrophically (eval: "Wonder Woman at Comic-Con" ranked 180th by vectors
alone). BM25 rescues those; RRF blends both so neither failure mode dominates.

Citation validation (X2): the model cites excerpt numbers + a timestamp; we keep
only citations whose excerpt is in the retrieved set and whose timestamp is a real
segment timestamp of that chunk (else fall back to the chunk's ts_start). The
snippet is a verbatim slice of the chunk text — never model-generated.
"""
import os
import re
import json
import math
import urllib.request
import urllib.error
from pathlib import Path

import numpy as np

_DIR = Path(__file__).resolve().parent
# embeddings live in data/rag/ at the repo root; on Vercel they must be bundled
# via includeFiles (see vercel.json). Resolve from repo root, fall back to api/.
_CANDIDATES = [_DIR.parent / "data" / "rag", _DIR / "rag", _DIR]


def _find(name):
    for d in _CANDIDATES:
        p = d / name
        if p.exists():
            return p
    return _CANDIDATES[0] / name


VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3"
ANSWER_K = 15
FUSE_N = 50          # candidates pulled from each signal before RRF
RRF_K = 60           # standard RRF constant
_EMBED_TIMEOUT = 4   # seconds; fail open like the Redis client

# No vector-similarity floor: in hybrid mode it would suppress exactly the
# low-vector-sim / high-BM25 hits (e.g. "Wonder Woman at Comic-Con"). Off-topic
# is handled by the model + the facts system prompt (verified: it declines).

# ── module-global state (loaded once per warm container) ──────────────────────
_M = None            # (N, dim) float32 unit vectors (contextual matrix)
_ROWS = None         # list of per-chunk metadata dicts
_CORPUS_HASH = None
_BM25 = None         # dict: {N, avgdl, k1, b, doc_len, df, postings}
_HOSTS = None        # dict: {Conan:{...}, Sona:{...}, Matt:{...}} aggregate profiles


def _load():
    global _M, _ROWS, _CORPUS_HASH, _BM25
    if _M is not None:
        return
    npz = np.load(_find("embeddings.npz"), allow_pickle=True)
    meta = json.loads(_find("chunks_meta.json").read_text(encoding="utf-8"))
    mat = npz["ctx_int8"].astype(np.float32) / float(npz["scale"])
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    _M = mat / norms
    _ROWS = meta["rows"]
    _CORPUS_HASH = meta["corpus_hash"]
    try:
        _BM25 = json.loads(_find("bm25.json").read_text(encoding="utf-8"))
    except Exception:
        _BM25 = None   # vector-only if the BM25 index is missing (fail soft)
    global _HOSTS
    try:
        _HOSTS = json.loads(_find("host_profiles.json").read_text(encoding="utf-8"))
    except Exception:
        _HOSTS = {}    # no host context if profiles missing (fail soft)


# Tokenizer MUST stay byte-identical to scripts/build_bm25.tokenize (duplicated
# because the serverless function can't import scripts/). Change both together.
_STOP = set((
    "a an the of to in on at for and or but is are was were be been being this "
    "that these those it its as with from by about into over under then than so "
    "if i you he she we they them his her their our your my me do does did has "
    "have had will would can could should what which who whom when where why how "
    "there here not no yes about up out off again once"
).split())


def _tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) > 1 and t not in _STOP]


def _bm25_ranked(question, n=FUSE_N):
    """Return up to n doc indices ranked by BM25 over the contextual index."""
    if not _BM25:
        return []
    N, avgdl = _BM25["N"], _BM25["avgdl"] or 1.0
    k1, b = _BM25["k1"], _BM25["b"]
    doc_len, df, postings = _BM25["doc_len"], _BM25["df"], _BM25["postings"]
    scores = {}
    for term in set(_tokenize(question)):
        plist = postings.get(term)
        if not plist:
            continue
        idf = math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
        for doc, tf in plist:
            denom = tf + k1 * (1 - b + b * doc_len[doc] / avgdl)
            scores[doc] = scores.get(doc, 0.0) + idf * (tf * (k1 + 1)) / denom
    return sorted(scores, key=lambda d: -scores[d])[:n]


def _rrf(vec_ranked, bm25_ranked, out=ANSWER_K):
    """Reciprocal rank fusion of two ranked index lists."""
    fused = {}
    for rank, doc in enumerate(vec_ranked, 1):
        fused[doc] = fused.get(doc, 0.0) + 1.0 / (RRF_K + rank)
    for rank, doc in enumerate(bm25_ranked, 1):
        fused[doc] = fused.get(doc, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(fused, key=lambda d: -fused[d])[:out]


def corpus_hash():
    _load()
    return _CORPUS_HASH


# Voyage key may be stored under any of these names (this project uses
# non-canonical names, e.g. the Anthropic key is `CLAUDE`/`Anthropic_API`).
_VOYAGE_KEY_NAMES = ("VOYAGE_API_KEY", "VoyageAPI", "VOYAGEAI_API_KEY", "VOYAGE_KEY")


def _voyage_key():
    for name in _VOYAGE_KEY_NAMES:
        v = os.environ.get(name)
        if v:
            return v
    return ""


def _embed_query(question):
    """Voyage query embedding as a unit vector, or None on any failure (fail open)."""
    key = _voyage_key()
    if not key:
        return None
    payload = json.dumps({"input": [question], "model": VOYAGE_MODEL,
                          "input_type": "query"}).encode("utf-8")
    try:
        req = urllib.request.Request(
            VOYAGE_URL, data=payload,
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=_EMBED_TIMEOUT) as resp:
            v = np.array(json.loads(resp.read())["data"][0]["embedding"],
                         dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n else None
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError):
        return None


def retrieve(question, k=ANSWER_K):
    """Hybrid retrieval. Return (status, chunks).

    status: "ok"          -> chunks is the fused top-k
            "unavailable" -> query embedding failed; caller falls open to the
                            facts-only answer. chunks is [].

    No abstain: off-topic is handled by the model + facts system prompt. Vector
    and BM25 each contribute up to FUSE_N candidates, fused via RRF.
    """
    _load()
    qv = _embed_query(question)
    if qv is None:
        return "unavailable", []
    sims = _M @ qv
    vec_ranked = [int(i) for i in np.argsort(-sims)[:FUSE_N]]
    bm25_ranked = _bm25_ranked(question, FUSE_N)
    fused = _rrf(vec_ranked, bm25_ranked, out=k) if bm25_ranked else vec_ranked[:k]
    chunks = []
    for rank, i in enumerate(fused, 1):
        r = dict(_ROWS[i])
        r["_score"] = float(sims[i])
        r["_n"] = rank
        chunks.append(r)
    return "ok", chunks


# ── host profiles (Phase 3 cross-episode synthesis) ──────────────────────────

def host_context(question):
    """If the question is about a recurring host (Conan/Sona/Matt), return that
    host's precomputed cross-episode profile as a context block, else "". This
    gives synthesis questions comprehensive coverage that top-15 chunks miss."""
    _load()
    if not _HOSTS:
        return ""
    blocks = []
    for host in ("Conan", "Sona", "Matt"):
        if host not in _HOSTS:
            continue
        if not re.search(r"\b" + host + r"\b", question, re.I):
            continue
        p = _HOSTS[host]
        parts = [f"PROFILE — {host} (aggregated across all episodes):"]
        if p.get("summary"):
            parts.append(p["summary"])
        for label, key in (("Advice/opinions", "advice"),
                           ("Stories", "stories"),
                           ("Recurring themes", "recurring_themes"),
                           ("Facts", "facts")):
            items = p.get(key) or []
            if items:
                parts.append(label + ": " + "; ".join(items[:8]))
        blocks.append("\n".join(parts))
        if len(blocks) >= 2:   # cap tokens if multiple hosts named
            break
    return "\n\n".join(blocks)


# ── prompt assembly + citation validation ────────────────────────────────────

def build_user_message(question, chunks, host_ctx=""):
    """Excerpts (numbered) + question, for the UNCACHED user turn (A1). An
    optional host profile block is prepended for host-synthesis questions."""
    lines = []
    if host_ctx:
        lines += [host_ctx, ""]
    lines += [
        "Answer the question using ONLY the excerpts below plus the fan list in "
        "your instructions. Be faithful; do not invent details.",
        "After your answer, on a new line output SOURCES: with the excerpt "
        "numbers you actually used and the timestamp you are citing, e.g. "
        "`SOURCES: 1@00:21:05, 3@00:24:10`.",
        "If the excerpts do not contain the answer, say you don't have transcript "
        "evidence for that and output `SOURCES:` with nothing after it.",
        "",
        "EXCERPTS:",
    ]
    for c in chunks:
        lines.append(f'[{c["_n"]}] (Fan: {c.get("fan_name","?")}, '
                     f'Episode: "{c.get("episode_title","?")}")')
        lines.append(c.get("text", ""))
        lines.append("")
    lines.append(f"QUESTION: {question}")
    return "\n".join(lines)


_SEG_RE = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\](?:\s+(?:Speaker \d+|spk_\d+):)?\s*\n(.*?)(?=\n\[\d|\Z)", re.DOTALL)


def _segments_of(chunk):
    """Parse a chunk's text back into {ts: verbatim_segment_text}."""
    out = {}
    for ts, txt in _SEG_RE.findall(chunk.get("text", "")):
        out[ts] = " ".join(txt.split())
    return out


def split_answer_sources(raw):
    """Split the model output into (answer_text, sources_line)."""
    m = re.search(r"(?im)^\s*SOURCES:\s*(.*)$", raw)
    if not m:
        return raw.strip(), ""
    return raw[:m.start()].strip(), m.group(1).strip()


def build_citations(sources_line, chunks):
    """Validate `n@ts` tokens against the retrieved chunks. Drop anything not in
    the retrieved set; fall back to a chunk's ts_start if the cited ts isn't a
    real segment timestamp. Snippet is verbatim chunk text."""
    by_n = {c["_n"]: c for c in chunks}
    citations, seen = [], set()
    for tok in re.findall(r"(\d+)\s*(?:@\s*(\d{1,2}:\d{2}(?::\d{2})?))?", sources_line):
        n = int(tok[0])
        if n not in by_n:
            continue                      # hallucinated / out-of-range -> drop
        c = by_n[n]
        segs = _segments_of(c)
        ts = tok[1] if tok[1] in segs else c.get("ts_start", "")
        if (n, ts) in seen:
            continue
        seen.add((n, ts))
        snippet = segs.get(ts) or next(iter(segs.values()), c.get("text", ""))
        citations.append({
            "episode_title": c.get("episode_title", ""),
            "fan_name": c.get("fan_name", ""),
            "timestamp": ts,
            "snippet": snippet[:240],
        })
    return citations
