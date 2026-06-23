#!/usr/bin/env python3
"""build_bm25.py — offline contextual-BM25 index over the chunk corpus.

Pairs with the vector matrix: at query time api/retrieval.py fuses vector cosine
and BM25 via reciprocal rank fusion (RRF). BM25 rescues exact-term / proper-noun
queries that embeddings occasionally miss catastrophically (e.g. "Wonder Woman at
Comic-Con" ranked 180th by vectors alone).

"Contextual" BM25 = indexed over contextual_text (blurb + chunk), same text the
embeddings use, so both signals see the same enriched content.

Doc order is aligned to the embeddings matrix (embeddings.npz chunk_ids order) so
a BM25 doc index == the vector matrix row index == chunks_meta row index.

Output: data/rag/bm25.json
  {N, avgdl, k1, b, doc_len:[...], df:{term:count}, postings:{term:[[doc,tf],...]}}

The tokenizer here MUST stay byte-identical to retrieval._tokenize (duplicated
there because the serverless function can't import scripts/). Change both together.
"""
import json
import re
import math
import numpy as np

CONTEXTUAL = "data/rag/chunks_contextual.jsonl"
NPZ = "data/rag/embeddings.npz"
OUT = "data/rag/bm25.json"
K1, B = 1.5, 0.75

# Small English stopword list. Keep in sync with retrieval._STOP.
STOP = set((
    "a an the of to in on at for and or but is are was were be been being this "
    "that these those it its as with from by about into over under then than so "
    "if i you he she we they them his her their our your my me do does did has "
    "have had will would can could should what which who whom when where why how "
    "there here not no yes about up out off again once"
).split())


def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) > 1 and t not in STOP]


def main():
    npz = np.load(NPZ, allow_pickle=True)
    order = [str(c) for c in npz["chunk_ids"]]            # canonical doc order
    ctx = {}
    for line in open(CONTEXTUAL, encoding="utf-8"):
        r = json.loads(line)
        ctx[r["chunk_id"]] = r.get("contextual_text") or r.get("text", "")

    postings = {}          # term -> {doc_idx: tf}
    doc_len = []
    for i, cid in enumerate(order):
        toks = tokenize(ctx.get(cid, ""))
        doc_len.append(len(toks))
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        for t, c in tf.items():
            postings.setdefault(t, {})[i] = c

    df = {t: len(d) for t, d in postings.items()}
    avgdl = sum(doc_len) / len(doc_len) if doc_len else 0
    out = {
        "N": len(order), "avgdl": avgdl, "k1": K1, "b": B,
        "doc_len": doc_len, "df": df,
        "postings": {t: [[doc, c] for doc, c in sorted(d.items())]
                     for t, d in postings.items()},
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"))
    import os
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB)")
    print(f"  docs={len(order)} terms={len(df)} avgdl={avgdl:.1f}")
    # sanity: a known unique term should map to its episode
    for probe in ("meow", "trotsky", "danhausen"):
        docs = [order[d] for d, _ in out["postings"].get(probe, [])]
        print(f"  '{probe}' -> {docs[:3]}")


if __name__ == "__main__":
    main()
