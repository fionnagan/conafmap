#!/usr/bin/env python3
"""contextualize_chunks.py — add contextual + metadata-only text to each chunk.

For every chunk we produce TWO situated variants of the text, so the smoke eval
(X1) can A/B whether the LLM contextualizer earns its place on this corpus:

  metadata_text  — cheap baseline, NO LLM. Prepends the chunk's own frontmatter
                   (episode, fan, location, occupation, date) to the raw chunk.
  contextual_text — the Anthropic contextual-retrieval technique. One Claude call
                   per chunk that reuses a PROMPT-CACHED full-transcript prefix and
                   returns a 1-line blurb situating the chunk; blurb + raw chunk.

raw_text is the chunk text unchanged. Nothing is discarded.

Cost control: the full episode transcript is sent once per episode as a cached
block (cache-write 1.25x), then read (cache-read 0.10x) for every other chunk in
that episode. Run `--limit 1` first to see real cost before the full corpus.

Input:  data/rag/chunks.jsonl
Output: data/rag/chunks_contextual.jsonl  (same rows + metadata_text, blurb,
        contextual_text). Incremental + resumable (--resume skips done chunk_ids).

Auth: reads ANTHROPIC_API_KEY from the environment or .env.local. This script
never prints or stores the key.
"""
import os
import re
import sys
import glob
import json
import argparse

import anthropic

CHUNKS_IN = "data/rag/chunks.jsonl"
OUT_FILE = "data/rag/chunks_contextual.jsonl"
NORM_DIR = "data/transcripts/normalized"
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 120

# Haiku pricing per million tokens (mirrors api/ask.py).
_IN, _OUT = 0.80, 4.00
_CACHE_WRITE, _CACHE_READ = _IN * 1.25, _IN * 0.10

CHUNK_PROMPT = (
    "Here is the chunk we want to situate within the whole transcript:\n"
    "<chunk>\n{chunk}\n</chunk>\n"
    "Give a short, succinct one-sentence context (who is talking and about what, "
    "and where it sits in the conversation) to situate this chunk within the "
    "overall episode for the purposes of improving search retrieval. "
    "Answer ONLY with the context sentence, nothing else."
)


def load_env_local():
    """Populate os.environ from .env.local for any KEY=VALUE not already set."""
    if not os.path.exists(".env.local"):
        return
    for line in open(".env.local", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def strip_frontmatter_body(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def slug_to_transcript():
    """Map episode_slug -> full normalized body text (the cached <document>)."""
    out = {}
    for path in glob.glob(os.path.join(NORM_DIR, "*.md")):
        text = open(path, encoding="utf-8").read()
        sm = re.search(r"^slug:\s*(.+)$", text, re.MULTILINE)
        if sm:
            out[sm.group(1).strip()] = strip_frontmatter_body(path)
    return out


def metadata_prefix(row):
    loc = row.get("fan_location", "")
    occ = row.get("fan_occupation", "")
    who = row.get("fan_name", "")
    title = row.get("episode_title", "")
    date = row.get("date", "")
    sentence = f'From the "Conan O\'Brien Needs a Fan" episode "{title}" ({date})'
    if who:
        person = who + (f", a {occ}" if occ else "")
        person += f" from {loc}" if loc else ""
        sentence += f" with fan {person}"
    return sentence + "."


def contextualize(client, doc, chunk_text):
    """One cached call: returns (blurb, usage).

    The transcript lives in a CACHED system block (caching a user-turn block
    silently fails to cache for this model/SDK; the system block caches reliably,
    verified via cache_creation/cache_read usage). The first chunk of an episode
    pays cache-write 1.25x; the rest read at 0.10x.
    """
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{
            "type": "text",
            "text": f"<transcript>\n{doc}\n</transcript>",
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": CHUNK_PROMPT.format(chunk=chunk_text),
        }],
    )
    return resp.content[0].text.strip(), resp.usage


def cost_of(u):
    return (getattr(u, "input_tokens", 0) * _IN
            + getattr(u, "cache_creation_input_tokens", 0) * _CACHE_WRITE
            + getattr(u, "cache_read_input_tokens", 0) * _CACHE_READ
            + getattr(u, "output_tokens", 0) * _OUT) / 1_000_000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="process only first N episodes")
    ap.add_argument("--resume", action="store_true", help="skip chunk_ids already in output")
    args = ap.parse_args()

    load_env_local()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ERROR: ANTHROPIC_API_KEY not set (env or .env.local).")
    client = anthropic.Anthropic()

    rows = [json.loads(l) for l in open(CHUNKS_IN, encoding="utf-8")]
    transcripts = slug_to_transcript()

    done = set()
    mode = "w"
    if args.resume and os.path.exists(OUT_FILE):
        done = {json.loads(l)["chunk_id"] for l in open(OUT_FILE, encoding="utf-8")}
        mode = "a"
        print(f"resume: {len(done)} chunks already done")

    # group by episode, preserve order
    episodes = []
    seen = {}
    for r in rows:
        s = r["episode_slug"]
        if s not in seen:
            seen[s] = len(episodes)
            episodes.append((s, []))
        episodes[seen[s]][1].append(r)
    if args.limit:
        episodes = episodes[:args.limit]

    total_cost = 0.0
    n_done = 0
    buckets = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    out = open(OUT_FILE, mode, encoding="utf-8")
    for slug, chunks in episodes:
        doc = transcripts.get(slug)
        if doc is None:
            print(f"  WARN: no transcript for slug {slug}, skipping {len(chunks)} chunks")
            continue
        for r in chunks:
            if r["chunk_id"] in done:
                continue
            blurb, usage = contextualize(client, doc, r["text"])
            total_cost += cost_of(usage)
            buckets["input"] += getattr(usage, "input_tokens", 0)
            buckets["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0)
            buckets["cache_read"] += getattr(usage, "cache_read_input_tokens", 0)
            buckets["output"] += getattr(usage, "output_tokens", 0)
            r["metadata_text"] = metadata_prefix(r) + "\n\n" + r["text"]
            r["blurb"] = blurb
            r["contextual_text"] = blurb + "\n\n" + r["text"]
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()
            n_done += 1
        print(f"  {slug}: {len(chunks)} chunks | running cost ${total_cost:.4f}")
    out.close()
    print(f"\ntokens: {buckets}")
    print(f"\nDone. {n_done} chunks contextualized. Total cost ${total_cost:.4f}")
    if n_done:
        print(f"Projected full-corpus cost from this run: "
              f"${total_cost / n_done * len(rows):.2f} for {len(rows)} chunks")


if __name__ == "__main__":
    main()
