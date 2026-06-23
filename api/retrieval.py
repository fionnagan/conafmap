"""api/retrieval.py — brute-force contextual retrieval over the committed matrix.

Loaded lazily and held module-global so warm invocations reuse the dequantized
matrix (A3). No vector DB: cosine over ~3.3k unit vectors is single-digit ms.

Pipeline (called by api/ask.py on a cache miss):
  embed query (Voyage voyage-3, fail-open) -> cosine top-K -> abstain if top < floor.

Citation validation (X2): the model cites excerpt numbers + a timestamp; we keep
only citations whose excerpt is in the retrieved set and whose timestamp is a real
segment timestamp of that chunk (else fall back to the chunk's ts_start). The
snippet is a verbatim slice of the chunk text — never model-generated.
"""
import os
import re
import json
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
# Abstention floor — calibrated from the smoke eval (X4): on-topic top-1 cosine
# ran 0.42-0.62, off-topic peaked at 0.38. Floor sits below on-topic to avoid
# false abstentions on weaker-but-valid queries; the model-level "no transcript
# evidence" reply is the backstop for the 0.35-0.42 gray zone.
RETRIEVAL_FLOOR = 0.35
_EMBED_TIMEOUT = 4  # seconds; fail open like the Redis client

# ── module-global state (loaded once per warm container) ──────────────────────
_M = None            # (N, dim) float32 unit vectors (contextual matrix)
_ROWS = None         # list of per-chunk metadata dicts
_CORPUS_HASH = None


def _load():
    global _M, _ROWS, _CORPUS_HASH
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
    """Return (status, chunks).

    status: "ok"        -> chunks is the top-k retrieved (above the floor)
            "abstain"   -> nothing relevant enough; chunks is []
            "unavailable" -> query embedding failed; caller should fall open to
                            the facts-only answer. chunks is [].
    """
    _load()
    qv = _embed_query(question)
    if qv is None:
        return "unavailable", []
    sims = _M @ qv
    top = np.argsort(-sims)[:k]
    if float(sims[top[0]]) < RETRIEVAL_FLOOR:
        return "abstain", []
    chunks = []
    for rank, i in enumerate(top, 1):
        r = dict(_ROWS[int(i)])
        r["_score"] = float(sims[int(i)])
        r["_n"] = rank
        chunks.append(r)
    return "ok", chunks


# ── prompt assembly + citation validation ────────────────────────────────────

def build_user_message(question, chunks):
    """Excerpts (numbered) + question, for the UNCACHED user turn (A1)."""
    lines = [
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
