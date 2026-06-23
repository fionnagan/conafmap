#!/usr/bin/env python3
"""run_eval.py — retrieval eval: vector-only vs hybrid (vector + BM25 RRF).

Uses the PRODUCTION retrieval internals (api/retrieval.py) so the eval can't
drift from what actually ships. Reports, per question, the rank of the gold
episode under vector-only and under hybrid, plus aggregate hit@5 / hit@15 / MRR.

Off-topic questions (gold_slug=null) report the top-1 vector cosine for the
record (no floor is used in hybrid retrieval).

Auth: VOYAGE_API_KEY from env or .env.local. Read-only over committed indexes.
Usage: python3 scripts/run_eval.py
"""
import os
import sys
import json

import numpy as np

sys.path.insert(0, "api")
import retrieval as R   # noqa: E402

EVAL = "eval/questions.jsonl"
KS = (5, 15)


def load_env_local():
    if not os.path.exists(".env.local"):
        return
    for line in open(".env.local", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def rank_of(order, gold):
    """1-based rank of the first row whose episode_slug == gold, else None."""
    for rank, i in enumerate(order, 1):
        if R._ROWS[i]["episode_slug"] == gold:
            return rank
    return None


def main():
    load_env_local()
    if not R._voyage_key():
        sys.exit("ERROR: Voyage key not set (env or .env.local).")
    R._load()
    if not R._BM25:
        sys.exit("ERROR: bm25.json not loaded — run scripts/build_bm25.py first.")

    qs = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
    vec_ranks, hyb_ranks = [], []
    offtopic_top1 = []

    print(f"{'Q':52} {'vec':>5} {'hybrid':>7}")
    print("-" * 70)
    for item in qs:
        qv = R._embed_query(item["question"])
        sims = R._M @ qv
        vec_order = [int(i) for i in np.argsort(-sims)]
        vec_top = vec_order[:R.FUSE_N]
        bm25_top = R._bm25_ranked(item["question"], R.FUSE_N)
        hyb_order = R._rrf(vec_top, bm25_top, out=len(vec_top) + len(bm25_top))

        gold = item["gold_slug"]
        if gold:
            vr = rank_of(vec_order, gold)
            hr = rank_of(hyb_order, gold)
            vec_ranks.append(vr)
            hyb_ranks.append(hr)
            flag = "  <-- rescue" if (vr and vr > 15 and hr and hr <= 15) else ""
            print(f"{item['question'][:50]:52} {str(vr):>5} {str(hr):>7}{flag}")
        else:
            offtopic_top1.append(float(sims[vec_order[0]]))
            print(f"{item['question'][:50]:52} {'-':>5} {'-':>7}   [offtopic vec_top1={sims[vec_order[0]]:.3f}]")

    def agg(ranks, k):
        hit = sum(1 for r in ranks if r is not None and r <= k)
        return hit, len(ranks), (hit / len(ranks) if ranks else 0)

    print("\n=== vector-only vs hybrid (labelled Qs) ===")
    for name, ranks in (("vector", vec_ranks), ("hybrid", hyb_ranks)):
        line = f"  {name:7}"
        for k in KS:
            h, n, rate = agg(ranks, k)
            line += f"  hit@{k}={h}/{n} ({rate:.0%})"
        mrr = np.mean([1.0 / r for r in ranks if r]) if ranks else 0
        line += f"  MRR={mrr:.3f}"
        print(line)

    fixed = [(q["question"], v, h) for q, v, h in zip(
        [x for x in qs if x["gold_slug"]], vec_ranks, hyb_ranks)
        if v and v > 15 and h and h <= 15]
    if fixed:
        print("\n  hybrid rescued (vector miss -> hybrid hit@15):")
        for q, v, h in fixed:
            print(f"    {q[:55]}: vec {v} -> hybrid {h}")
    regressed = [(q["question"], v, h) for q, v, h in zip(
        [x for x in qs if x["gold_slug"]], vec_ranks, hyb_ranks)
        if v and v <= 15 and (not h or h > 15)]
    if regressed:
        print("\n  REGRESSED (vector hit@15 -> hybrid miss):")
        for q, v, h in regressed:
            print(f"    {q[:55]}: vec {v} -> hybrid {h}")


if __name__ == "__main__":
    main()
