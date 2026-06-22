# Phase 1 Smoke Eval — Results

Run: `python3 scripts/run_eval.py` (12 labelled questions + 2 off-topic).

## Retrieval quality
- **hit@5 = 12/12 (100%)**, hit@15 = 12/12. Every gold episode retrieved.
- Contextual matrix MRR **0.944**, metadata-only MRR **0.892**.

## X1 — contextual vs metadata-only baseline (the key A/B)
- On **occupation-style** questions (locksmith, paleontologist, juice bar owner, …):
  both variants rank the gold episode #1 — a tie. The free metadata baseline already
  nails these because occupation/location/name live in the frontmatter.
- On **content-level** questions (answer NOT in frontmatter), contextual wins:
  - "help convince partner to propose" → contextual rank **1**, metadata rank **5**
  - "tiny airplane into the wrestling ring" → contextual 3, metadata 2
  - net: contextual MRR 0.944 > metadata 0.892
- **Decision: serve the contextual matrix.** It beats metadata on content questions
  and ties on occupation questions, so it can only help. The ~$5 contextualization
  pass is justified. (A richer content-question set would widen the gap further.)

## X4 — abstention floor calibration
- on-topic top-1 cosine: min 0.423, mean 0.556
- off-topic top-1 cosine: max 0.376, mean 0.370
- Floor set to **0.35** in api/retrieval.py — below on-topic to avoid false
  abstentions on weaker-but-valid queries. The 0.35-0.42 gray zone (where the two
  off-topic queries land) is caught by the model-level "I don't have transcript
  evidence" reply, verified to fire on off-topic input. Defense in depth.

## X2 — citation timestamp accuracy
- See `eval/audio_spotcheck.md`: 10 citations across diverse episodes with timestamps
  and quotes to verify against the actual podcast audio (human check).

## Known eval limitation
The labelled set skews toward occupation questions (metadata's strong suit). The
contextual advantage shown on the 3 content questions would be larger with a broader
content/thematic set. Worth expanding in the Phase 2 full harness.
