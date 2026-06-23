#!/usr/bin/env python3
"""Unit tests for chunk_transcripts.py — run: python3 scripts/test_chunk_transcripts.py"""
import chunk_transcripts as C


def _seg(ts, sp, words):
    return (ts, sp, " ".join(["w"] * words))


def test_parse_speaker_labeled():
    body = (
        "# Transcript: X\n\n---\n\n"
        "[00:00:03] Speaker 1:\n\nHello there friend.\n\n"
        "[00:00:08] Speaker 2:\n\nHi back to you.\n"
    )
    segs = C.parse_segments(body)
    assert len(segs) == 2, segs
    assert segs[0] == ("00:00:03", "Speaker 1", "Hello there friend."), segs[0]
    assert segs[1][1] == "Speaker 2"
    print("ok test_parse_speaker_labeled")


def test_parse_no_speaker_label():
    body = "# Transcript: X\n\n---\n\n[00:00:03]\n\nClean prose block here.\n"
    segs = C.parse_segments(body)
    assert len(segs) == 1 and segs[0][1] is None, segs
    assert segs[0][2] == "Clean prose block here."
    print("ok test_parse_no_speaker_label")


def test_parse_mmss_and_spk():
    body = "# Transcript: X\n\n---\n\n[00:03] spk_0:\n\nMusixmatch style line.\n"
    segs = C.parse_segments(body)
    assert segs[0][0] == "00:03" and segs[0][1] == "spk_0", segs
    print("ok test_parse_mmss_and_spk")


def test_chunk_groups_to_target():
    # five 70-word segments, TARGET 180: chunk1 closes after 3rd (210w),
    # chunk2 = remaining 2 (140w, above runt floor so not merged)
    segs = [_seg(f"00:00:0{i}", "Speaker 1", 70) for i in range(5)]
    chunks = C.chunk_segments(segs)
    assert len(chunks) == 2, [len(c) for c in chunks]
    assert len(chunks[0]) == 3 and len(chunks[1]) == 2, [len(c) for c in chunks]
    print("ok test_chunk_groups_to_target")


def test_long_turn_not_split():
    # a single 500-word segment must remain one intact chunk
    segs = [_seg("00:01:00", "Speaker 1", 500)]
    chunks = C.chunk_segments(segs)
    assert len(chunks) == 1 and len(chunks[0]) == 1
    assert chunks[0][0][2].split().__len__() == 500
    print("ok test_long_turn_not_split")


def test_runt_tail_merged():
    # a 200w chunk then a 10w runt tail => merged into one chunk
    segs = [_seg("00:00:00", "Speaker 1", 200), _seg("00:05:00", "Speaker 2", 10)]
    chunks = C.chunk_segments(segs)
    assert len(chunks) == 1, [len(c) for c in chunks]
    assert len(chunks[0]) == 2
    print("ok test_runt_tail_merged")


def test_non_runt_tail_kept():
    # a 200w chunk then a 100w tail (>= MIN_TAIL_WORDS) => stays separate
    segs = [_seg("00:00:00", "Speaker 1", 200), _seg("00:05:00", "Speaker 2", 100)]
    chunks = C.chunk_segments(segs)
    assert len(chunks) == 2, [len(c) for c in chunks]
    print("ok test_non_runt_tail_kept")


def test_chunk_text_keeps_markers():
    chunk = [("00:01:00", "Speaker 1", "Question here?"),
             ("00:01:05", "Speaker 2", "Answer here.")]
    txt = C.render_chunk_text(chunk)
    assert "[00:01:00] Speaker 1:" in txt and "[00:01:05] Speaker 2:" in txt
    assert "Question here?" in txt and "Answer here." in txt
    print("ok test_chunk_text_keeps_markers")


def test_uniqueness_guard():
    # two chunks sharing the same ts_start must not collide silently
    rows = [{"chunk_id": "ep#00:01:00"}, {"chunk_id": "ep#00:01:00"},
            {"chunk_id": "ep#00:02:00"}]
    collisions = C.ensure_unique_ids(rows)
    ids = [r["chunk_id"] for r in rows]
    assert collisions == 1, collisions
    assert len(ids) == len(set(ids)), ids
    assert "ep#00:01:00-2" in ids
    print("ok test_uniqueness_guard")


if __name__ == "__main__":
    for name in [n for n in dir() if n.startswith("test_")]:
        globals()[name]()
    print("ALL PASS")
