#!/usr/bin/env python3
"""chunk_transcripts.py — turn normalized transcripts into retrieval chunks.

Reads ONLY data/transcripts/normalized/*.md (the single canonical grammar:
`[HH:MM:SS]` optionally `+ Speaker N:`, blank line, text block). Does NOT touch
raw/ — the five source-format complexity stays sealed in normalize_transcripts.py.

Chunking strategy
-----------------
The atomic unit is one timestamp segment. We never split a segment across chunks
("never split mid-turn"). We accumulate whole segments into a chunk until the
running word count reaches TARGET_WORDS, then start a new chunk. A chunk may hold
a short multi-speaker exchange (good: keeps question + answer together); a single
long segment (e.g. an ad read) becomes its own chunk.

Each chunk keeps the inline `[HH:MM:SS]`/`Speaker N:` markers in its text and a
`segment_ts` list, so the request path can do per-segment citation (cite the
specific segment a quote came from) and citation validation (a cited timestamp
must exist in the chunk's segment_ts).

Output: data/rag/chunks.jsonl, one JSON object per line:
  {chunk_id, episode_slug, episode_title, fan_name, fan_location,
   fan_occupation, date, source, ts_start, segment_ts[], speakers[],
   chunk_index, word_count, text}
"""
import re
import os
import glob
import json

NORM_DIR = "data/transcripts/normalized"
OUT_DIR = "data/rag"
OUT_FILE = os.path.join(OUT_DIR, "chunks.jsonl")

# Aim for ~180-word chunks; close a chunk once it reaches this. A single segment
# longer than this becomes its own chunk (never split).
TARGET_WORDS = 180

# An episode's trailing remainder below this many words (a runt goodbye/outro) is
# merged back into the previous chunk rather than embedded as its own near-empty
# vector. Only ever applies to the last chunk of an episode.
MIN_TAIL_WORDS = 60

# `[00:01:23]` or `[00:01:23] Speaker 1:` or `[00:03] spk_0:`
SEGMENT_RE = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\](?:\s+(Speaker \d+|spk_\d+):)?\s*$")


def parse_frontmatter(text):
    """Return (frontmatter_dict, body_str). Minimal YAML — flat key: "value" pairs."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        km = re.match(r'^(\w+):\s*(.*)$', line)
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        fm[key] = val
    return fm, m.group(2)


def parse_segments(body):
    """Parse the body into [(ts, speaker_or_None, text), ...].

    Skips the `# Transcript:` header, the optional `**Episode description:**`
    line, and the `---` separator — only the segment grammar is parsed.
    """
    lines = body.splitlines()
    segments = []
    cur_ts = None
    cur_speaker = None
    cur_text = []

    def flush():
        if cur_ts is not None:
            txt = " ".join(" ".join(cur_text).split())  # collapse whitespace
            if txt:
                segments.append((cur_ts, cur_speaker, txt))

    for line in lines:
        m = SEGMENT_RE.match(line.strip())
        if m:
            flush()
            cur_ts = m.group(1)
            cur_speaker = m.group(2)
            cur_text = []
        elif cur_ts is not None:
            cur_text.append(line)
    flush()
    return segments


def chunk_segments(segments):
    """Group segments into chunks of ~TARGET_WORDS, never splitting a segment.

    Returns a list of chunks, each a list of (ts, speaker, text) segments.
    """
    chunks = []
    cur = []
    cur_words = 0
    for seg in segments:
        cur.append(seg)
        cur_words += len(seg[2].split())
        if cur_words >= TARGET_WORDS:
            chunks.append(cur)
            cur = []
            cur_words = 0
    if cur:
        chunks.append(cur)
    # Merge a runt trailing chunk into the previous one (episode outros, short
    # goodbyes) so we don't embed near-empty vectors.
    if len(chunks) >= 2:
        tail_words = sum(len(s[2].split()) for s in chunks[-1])
        if tail_words < MIN_TAIL_WORDS:
            chunks[-2].extend(chunks[-1])
            chunks.pop()
    return chunks


def render_chunk_text(chunk):
    """Re-emit a chunk's segments with inline markers preserved, so per-segment
    citation and validation have the timestamps available in the text."""
    parts = []
    for ts, speaker, text in chunk:
        head = f"[{ts}] {speaker}:" if speaker else f"[{ts}]"
        parts.append(f"{head}\n{text}")
    return "\n\n".join(parts)


def build_chunks_for_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, body = parse_frontmatter(text)
    segments = parse_segments(body)
    slug = fm.get("slug") or os.path.splitext(os.path.basename(path))[0]
    rows = []
    for idx, chunk in enumerate(chunk_segments(segments)):
        seg_ts = [s[0] for s in chunk]
        speakers = sorted({s[1] for s in chunk if s[1]})
        chunk_text = render_chunk_text(chunk)
        rows.append({
            "chunk_id": f"{slug}#{seg_ts[0]}",
            "episode_slug": slug,
            "episode_title": fm.get("episode_title", ""),
            "fan_name": fm.get("fan_name", ""),
            "fan_location": fm.get("fan_location", ""),
            "fan_occupation": fm.get("fan_occupation", ""),
            "date": fm.get("date_published", ""),
            "source": fm.get("source", ""),
            "ts_start": seg_ts[0],
            "segment_ts": seg_ts,
            "speakers": speakers,
            "chunk_index": idx,
            "word_count": sum(len(s[2].split()) for s in chunk),
            "text": chunk_text,
        })
    return rows


def ensure_unique_ids(rows):
    """chunk_id = {slug}#{ts_start}. Two chunks in one episode can share a
    ts_start only if two segments carry the same timestamp AND a chunk boundary
    falls between them. Guard against silent collision: suffix -2/-3 and warn.
    """
    seen = {}
    collisions = 0
    for r in rows:
        cid = r["chunk_id"]
        if cid in seen:
            seen[cid] += 1
            collisions += 1
            new_id = f"{cid}-{seen[cid]}"
            print(f"  WARN: duplicate chunk_id {cid} -> {new_id}")
            r["chunk_id"] = new_id
        else:
            seen[cid] = 1
    return collisions


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(NORM_DIR, "*.md")))
    all_rows = []
    for path in files:
        all_rows.extend(build_chunks_for_file(path))
    collisions = ensure_unique_ids(all_rows)

    # Hard assertion: ids must be globally unique after the guard.
    ids = [r["chunk_id"] for r in all_rows]
    assert len(ids) == len(set(ids)), "chunk_id uniqueness assertion FAILED"

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    wc = [r["word_count"] for r in all_rows]
    print(f"Wrote {len(all_rows)} chunks from {len(files)} episodes -> {OUT_FILE}")
    print(f"  collisions resolved: {collisions}")
    print(f"  words/chunk: min={min(wc)} max={max(wc)} avg={sum(wc)//len(wc)}")
    labeled = sum(1 for r in all_rows if r["speakers"])
    print(f"  chunks with speaker labels: {labeled}/{len(all_rows)}")


if __name__ == "__main__":
    main()
