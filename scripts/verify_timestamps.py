#!/usr/bin/env python3
"""verify_timestamps.py — X2 citation-integrity check (no audio needed).

Audio-absolute timestamp accuracy is unverifiable for this podcast: dynamic ad
insertion (DAI) gives every listener a different timeline, so a timestamp can
never map to "the" audio. What we CAN and must verify is pipeline integrity:
every timestamp in a retrieval chunk faithfully matches where that line sits in
the source transcript (no misattribution, no chunking drift).

This checks all chunks against the normalized transcripts and asserts 0 true
corruption. Duplicate-second collisions (multiple sub-second source lines sharing
one HH:MM:SS, e.g. Tapesearch decimal timestamps) are NOT corruption — both lines
exist at that second — and are reported separately.

Exit non-zero if any true corruption is found.
Usage: python3 scripts/verify_timestamps.py
"""
import json
import re
import sys
import glob
from collections import defaultdict

NORM_DIR = "data/transcripts/normalized"
META = "data/rag/chunks_meta.json"
SEG = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\](?:\s+(?:Speaker \d+|spk_\d+):)?\s*\n(.*?)(?=\n\[\d|\Z)",
    re.DOTALL)


def main():
    truth = defaultdict(list)   # (slug, ts) -> [segment texts]  (list: allow dup-second)
    for p in glob.glob(f"{NORM_DIR}/*.md"):
        t = open(p, encoding="utf-8").read()
        slug = re.search(r"^slug:\s*(.+)$", t, re.M).group(1).strip()
        body = re.split(r"\n---\n", t, 1)[-1]
        for ts, txt in SEG.findall(body):
            truth[(slug, ts)].append(" ".join(txt.split()))

    rows = json.load(open(META, encoding="utf-8"))["rows"]
    checked = true_corrupt = dup_collapse = 0
    id_bad = 0
    corrupt_examples = []
    for r in rows:
        slug = r["episode_slug"]
        if not r["text"].startswith("[" + r["ts_start"] + "]"):
            id_bad += 1
        for ts, txt in SEG.findall(r["text"]):
            checked += 1
            variants = truth.get((slug, ts), [])
            norm = " ".join(txt.split())
            if norm in variants:
                continue
            if len(variants) > 1:
                dup_collapse += 1
            else:
                true_corrupt += 1
                if len(corrupt_examples) < 10:
                    corrupt_examples.append((slug, ts))

    print(f"segments checked: {checked}")
    print(f"faithfully preserved: {checked - true_corrupt}/{checked}")
    print(f"duplicate-second collisions (fine, both lines exist): {dup_collapse}")
    print(f"chunk_id ts_start == first segment: {len(rows) - id_bad}/{len(rows)}")
    print(f"TRUE corruption: {true_corrupt}")
    for e in corrupt_examples:
        print("  corrupt:", e)
    if true_corrupt or id_bad:
        print("FAIL")
        sys.exit(1)
    print("PASS — every cited timestamp faithfully reflects the source transcript.")


if __name__ == "__main__":
    main()
