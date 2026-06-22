#!/usr/bin/env python3
"""run_eval.py — Phase 1 smoke eval for the RAG retrieval layer.

Answers three questions the eng review flagged:
  X1  — does the LLM contextual_text beat the free metadata_text baseline?
        (retrieve each query against BOTH matrices, compare hit@k)
  X4  — where should the abstention floor sit? (print top-1 score for on-topic
        factual queries vs off-topic queries; the floor goes between them)
  retrieval quality — hit@5 / hit@15 and the rank of the gold episode.

Gold label = the episode_slug that should appear in the retrieved chunks.
Off-topic questions (gold_slug=null) should score LOW (used for floor calibration).

Auth: VOYAGE_API_KEY from env or .env.local. Read-only over committed matrices.
Usage: python3 scripts/run_eval.py
"""
import os
import sys
import json
import urllib.request

import numpy as np

EVAL = "eval/questions.jsonl"
NPZ = "data/rag/embeddings.npz"
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
MODEL = "voyage-3"
KS = (5, 15)


def load_env_local():
    if not os.path.exists(".env.local"):
        return
    for line in open(".env.local", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def embed_query(q, key):
    payload = json.dumps({"input": [q], "model": MODEL,
                          "input_type": "query"}).encode("utf-8")
    req = urllib.request.Request(
        VOYAGE_URL, data=payload,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"}, method="POST")
    v = np.array(json.loads(urllib.request.urlopen(req, timeout=30).read())
                 ["data"][0]["embedding"], dtype=np.float32)
    return v / np.linalg.norm(v)


def unit(mat, scale):
    m = mat.astype(np.float32) / float(scale)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def gold_rank(sims, slugs, gold):
    order = np.argsort(-sims)
    for rank, i in enumerate(order, 1):
        if slugs[int(i)] == gold:
            return rank, float(sims[order[0]])
    return None, float(sims[order[0]])


def main():
    load_env_local()
    key = os.environ.get("VOYAGE_API_KEY")
    if not key:
        sys.exit("ERROR: VOYAGE_API_KEY not set (env or .env.local).")

    d = np.load(NPZ, allow_pickle=True)
    scale = float(d["scale"])
    ctx = unit(d["ctx_int8"], scale)
    meta = unit(d["meta_int8"], scale)
    slugs = [cid.split("#")[0] for cid in d["chunk_ids"]]

    qs = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
    results = {"ctx": [], "meta": []}
    ontopic_top1, offtopic_top1 = [], []

    print(f"{'Q':52} {'ctx rank':>9} {'meta rank':>10}")
    print("-" * 74)
    for item in qs:
        qv = embed_query(item["question"], key)
        cr, ctop = gold_rank(ctx @ qv, slugs, item["gold_slug"])
        mr, mtop = gold_rank(meta @ qv, slugs, item["gold_slug"])
        if item["gold_slug"]:
            results["ctx"].append(cr)
            results["meta"].append(mr)
            ontopic_top1.append(ctop)
        else:
            offtopic_top1.append(ctop)
        label = item["question"][:50]
        print(f"{label:52} {str(cr):>9} {str(mr):>10}"
              + ("   [offtopic top1 ctx=%.3f]" % ctop if not item["gold_slug"] else ""))

    def hitrate(ranks, k):
        hit = sum(1 for r in ranks if r is not None and r <= k)
        return hit, len(ranks), (hit / len(ranks) if ranks else 0)

    print("\n=== X1: contextual vs metadata-only (hit@k over factual/thematic Qs) ===")
    for variant in ("ctx", "meta"):
        line = f"  {variant:5}"
        for k in KS:
            h, n, rate = hitrate(results[variant], k)
            line += f"  hit@{k}={h}/{n} ({rate:.0%})"
        mrr = np.mean([1.0 / r for r in results[variant] if r]) if results[variant] else 0
        line += f"  MRR={mrr:.3f}"
        print(line)

    print("\n=== X4: abstention floor calibration (top-1 cosine, ctx matrix) ===")
    if ontopic_top1:
        print(f"  on-topic  min={min(ontopic_top1):.3f} mean={np.mean(ontopic_top1):.3f}")
    if offtopic_top1:
        print(f"  off-topic max={max(offtopic_top1):.3f} mean={np.mean(offtopic_top1):.3f}")
    if ontopic_top1 and offtopic_top1:
        lo, hi = max(offtopic_top1), min(ontopic_top1)
        rec = round((lo + hi) / 2, 2)
        print(f"  -> suggested floor between {lo:.3f} (offtopic max) and "
              f"{hi:.3f} (ontopic min); midpoint ~{rec}")


if __name__ == "__main__":
    main()
