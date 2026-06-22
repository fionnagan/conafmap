#!/usr/bin/env python3
"""Normalize all raw transcripts into a canonical [HH:MM:SS] (+ Speaker N:) format.

Reads data/transcripts/raw/*.md, leaves them untouched, writes normalized
copies to data/transcripts/normalized/*.md with identical frontmatter.
"""
import re
import os
import glob

RAW_DIR = "data/transcripts/raw"
OUT_DIR = "data/transcripts/normalized"


def split_frontmatter(text):
    m = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
    if not m:
        return "", text
    return m.group(0), text[m.end():]


def hhmmss(h, m, s):
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def normalize_happyscribe(body):
    # bare HH:MM:SS on its own line, blank line, prose block, repeated
    parts = re.split(r"(?m)^(\d{2}:\d{2}:\d{2})$", body)
    out = []
    # parts[0] is preamble (e.g. heading), then alternating ts, text
    out.append(parts[0])
    for i in range(1, len(parts), 2):
        ts = parts[i]
        text = parts[i + 1].strip()
        if not text:
            continue
        out.append(f"[{ts}]\n\n{text}\n")
    return "\n".join(out)


def normalize_podscripts(body):
    # inline "Starting point is HH:MM:SS" markers mid-prose
    segments = re.split(r"Starting point is (\d{2}:\d{2}:\d{2})\s*", body)
    out = [segments[0].strip()]
    pieces = []
    if out[0]:
        pieces.append(("00:00:00", out[0]))
    for i in range(1, len(segments), 2):
        ts = segments[i]
        text = segments[i + 1].strip() if i + 1 < len(segments) else ""
        if text:
            pieces.append((ts, text))
    return "\n\n".join(f"[{ts}]\n\n{text}" for ts, text in pieces)


def normalize_podscribe(body):
    # repeated: speaker_id, timestamp, text, in varying whitespace
    pattern = re.compile(
        r"(\d{1,3})\s+(\d{2}:\d{2}:\d{2})\s*\n*(.*?)(?=\n*\d{1,3}\s+\d{2}:\d{2}:\d{2}|\Z)",
        re.DOTALL,
    )
    out = []
    for sp, ts, text in pattern.findall(body):
        text = text.strip()
        if not text:
            continue
        out.append(f"[{ts}] Speaker {sp}:\n\n{text}")
    return "\n\n".join(out)


def normalize_musixmatch(body):
    pattern = re.compile(r"\[(\d{2}):(\d{2})\]\s*(spk_\d+):\s*(.*?)(?=\n\[\d{2}:\d{2}\]|\Z)", re.DOTALL)
    out = []
    for mm, ss, spk, text in pattern.findall(body):
        ts = hhmmss(0, mm, ss)
        text = text.strip()
        if not text:
            continue
        out.append(f"[{ts}] {spk}:\n\n{text}")
    return "\n\n".join(out)


def normalize_tapesearch(body):
    # "M:SS.f text" inline at start of each line/segment
    pattern = re.compile(r"(\d{1,2}):(\d{2})\.(\d)\s*(.*?)(?=\n*\d{1,2}:\d{2}\.\d|\Z)", re.DOTALL)
    out = []
    for m, s, frac, text in pattern.findall(body):
        ts = hhmmss(0, m, s)
        text = text.strip()
        if not text:
            continue
        out.append(f"[{ts}]\n\n{text}")
    return "\n\n".join(out)


def get_source_key(frontmatter):
    source = re.search(r"^source:\s*(\S+)", frontmatter, re.MULTILINE)
    fetched_via = re.search(r"^fetched_via:\s*(\S+)", frontmatter, re.MULTILINE)
    source = source.group(1) if source else ""
    fetched_via = fetched_via.group(1) if fetched_via else ""
    return source, fetched_via


def normalize_file(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    frontmatter, body = split_frontmatter(text)
    source, fetched_via = get_source_key(frontmatter)

    # Pull out the "# Transcript: ..." header (and optional description line)
    header_match = re.match(r"(.*?# Transcript:.*?\n(?:\*\*Episode description:.*?\n)?)\n*---\n*", body, re.DOTALL)
    if header_match:
        header = header_match.group(1).rstrip() + "\n"
        rest = body[header_match.end():]
    else:
        header = ""
        rest = body

    if source == "happyscribe":
        normalized_body = normalize_happyscribe(rest)
    elif source == "podscripts":
        normalized_body = normalize_podscripts(rest)
    elif source == "podscribe":
        normalized_body = normalize_podscribe(rest)
    elif source == "musixmatch":
        normalized_body = normalize_musixmatch(rest)
    elif source == "tapesearch":
        normalized_body = normalize_tapesearch(rest)
    else:
        raise ValueError(f"Unknown source '{source}' in {path}")

    out_text = frontmatter + header + "\n---\n\n" + normalized_body.strip() + "\n"
    return out_text


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.md")))
    failures = []
    for path in files:
        fname = os.path.basename(path)
        try:
            out_text = normalize_file(path)
        except Exception as e:
            failures.append((fname, str(e)))
            continue
        out_path = os.path.join(OUT_DIR, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_text)
    print(f"Normalized {len(files) - len(failures)}/{len(files)} files.")
    if failures:
        print("Failures:")
        for fname, err in failures:
            print(f"  {fname}: {err}")


if __name__ == "__main__":
    main()
