#!/usr/bin/env python3
"""
enrich_episodes.py — Full structured enrichment for fan episodes.

Generates for each fan episode:
  - summary            (180-450 words, structured narrative)
  - fan_questions      (array of structured Q&A objects with types & sentiment)
  - highlights_v2      (structured highlights with categories & virality scores)
  - episode_type       (classification: fan/celebrity/mixed)
  - quality_scores     (per-dimension 0-100 scores)
  - validation         (boolean gate checks)

Field-level upsert — never overwrites valid existing data.
Writes results to data/rich_data.json and logs to data/enrich_log.json.

Usage:
  python3 scripts/enrich_episodes.py [--dry-run] [--limit N] [--min-quality N]
    --dry-run         Read and log, write nothing
    --limit N         Process at most N episodes
    --min-quality N   Skip episodes where overall_quality >= N (default 80)
"""

import csv
import json
import os
import re
import sys
import time
import uuid
import urllib.request
import urllib.parse
from pathlib import Path

ROOT      = Path(__file__).parent.parent
DATA_DIR  = ROOT / 'data'
CSV_FILE  = DATA_DIR / 'episodes.csv'
RICH_FILE = DATA_DIR / 'rich_data.json'
LOG_FILE  = DATA_DIR / 'enrich_log.json'

# ── CLI args ──────────────────────────────────────────────────────────────────
DRY_RUN     = '--dry-run'  in sys.argv
LIMIT       = None
MIN_QUALITY = 80
for i, a in enumerate(sys.argv):
    if a == '--limit'       and i + 1 < len(sys.argv): LIMIT       = int(sys.argv[i+1])
    if a == '--min-quality' and i + 1 < len(sys.argv): MIN_QUALITY = int(sys.argv[i+1])


# ── URL helpers ───────────────────────────────────────────────────────────────

def fetch_url(url, timeout=12):
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'ConanFanMap/1.0 (+github.com/fionnagan/conafmap)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception:
        return ''


def make_slug(title):
    s = title.lower()
    s = re.sub(r"[''']", '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def get_source_text(title, desc=''):
    """Fetch TeamCoco page + HappyScribe transcript + RSS description."""
    slug = make_slug(title)
    sources = []

    tc_url  = f'https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes/{slug}'
    tc_text = fetch_url(tc_url)
    if tc_text and len(tc_text) > 500:
        clean = re.sub(r'<[^>]+>', ' ', tc_text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 200:
            sources.append(f"--- TeamCoco page ---\n{clean[:4000]}")

    hs_url  = f'https://podcasts.happyscribe.com/conan-o-brien-needs-a-friend/{slug}'
    hs_text = fetch_url(hs_url)
    if hs_text and len(hs_text) > 500:
        clean2 = re.sub(r'<[^>]+>', ' ', hs_text)
        clean2 = re.sub(r'\s+', ' ', clean2).strip()
        if len(clean2) > 200:
            sources.append(f"--- HappyScribe transcript ---\n{clean2[:6000]}")

    if desc and len(desc.strip()) > 20:
        desc_clean = re.sub(r'<[^>]+>', ' ', desc)
        desc_clean = re.sub(r'\s+', ' ', desc_clean).strip()
        sources.append(f"--- RSS description ---\n{desc_clean[:1000]}")

    return '\n\n'.join(sources)


# ── Claude ────────────────────────────────────────────────────────────────────

def extract_json_robust(raw):
    """Extract first valid JSON object from a Claude response."""
    # Strategy 1: markdown code fence
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    # Strategy 2: outermost braces
    start = raw.find('{')
    end   = raw.rfind('}')
    if start != -1 and end > start:
        try: return json.loads(raw[start:end+1])
        except Exception: pass
    return None


ENRICH_PROMPT = """You are a metadata writer for "Conan O'Brien Needs a Fan" podcast episodes.
A civilian fan calls in; Conan interviews them about their life, job, or unusual situation.
Conan always drives the conversation — fans rarely ask him anything back.

Episode: {title}
Fan: {name} — {location}
Occupation: {occupation}
Topic: {topic}

Source material:
{source_text}

─── SPEAKER ATTRIBUTION RULES ───
• fan_questions = ONLY questions the fan asked CONAN directly (e.g. "Have you ever been to Ireland?")
• Questions about the fan's own work/expertise/life = asked BY Conan — do NOT include as fan_questions
• When in doubt → fan_questions = []
• interactionType "fan-led" requires at least one verified fan-directed question to Conan

─── GENERATE THIS JSON OBJECT ───

{{
  "episode_type": {{
    "fan_episode": true,
    "celebrity_episode": false,
    "mixed_episode": false,
    "confidence": 0.95
  }},
  "summary": "SEE FIELD RULES BELOW",
  "fan_questions": [
    {{
      "question_id": "PLACEHOLDER_UUID",
      "question": "exact or close-paraphrase of the fan's question to Conan",
      "question_reframed_by_conan": null,
      "asked_by": "{name}",
      "conversation_context": "1-2 sentences of setup",
      "question_type": "advice|career|relationship|social|existential|comedic|storytelling|other",
      "sentiment": "positive|neutral|negative|mixed",
      "conan_response": {{
        "summary": "what Conan said in response",
        "quote": "memorable paraphrased line from Conan (30-500 chars)"
      }},
      "confidence": 0.85
    }}
  ],
  "highlights_v2": [
    {{
      "highlight_id": "PLACEHOLDER_UUID",
      "title": "4-7 word internal label",
      "summary": "SEE FIELD RULES BELOW",
      "category": "comedy|advice|emotional|awkward|absurd|storytelling|career|relationship|callback",
      "participants": ["Conan", "{name}"],
      "notable_quote": "memorable line or exchange (paraphrased fine if no transcript)",
      "virality_score": 70
    }}
  ],
  "quality_scores": {{
    "summary_quality": 0,
    "question_coverage": 0,
    "response_pairing_quality": 0,
    "highlight_quality": 0,
    "overall_quality": 0
  }},
  "validation": {{
    "has_summary": true,
    "has_questions": false,
    "has_highlights": true,
    "has_responses": false
  }}
}}

─── FIELD RULES ───

summary — 1 to 3 sentences maximum:
• Describe what this episode was BROADLY about — the overall arc, not a list of what happened
• Capture Conan's energy through his behavior or reactions, not generic description
• One specific, episode-only detail is worth more than any general claim
• FORBIDDEN OPENERS: "The conversation explores…" / "They discuss…" / "Conan and {name} talk about…"
• FORBIDDEN BOILERPLATE: "As with all episodes in this format, Conan drives the interview, drawing…"
  — never write template narration that could apply to any other episode
• FORBIDDEN DESCRIPTORS: "hilarious", "heartwarming", "insightful" unless the sentence names
  exactly what moment earns that description
• FORBIDDEN STRUCTURE: listing 2+ jokes or moments in sequence; recap bullet style
• DO NOT repeat any content that will appear in highlights_v2
• If source text is thin, write what is known — 1-2 honest sentences beats fabricated detail

highlights_v2 — 3 to 5 highlights, prioritise the strongest moments only:
• summary = ONE sentence per highlight. Land the moment directly — no preamble, no recap framing.
• Name the specific person, action, punchline, or reaction. Be concrete.
• Each highlight must surface a DISTINCT listener takeaway — no thematic overlap between highlights
• FORBIDDEN in summary text: category words as labels ("Comedy:", "Storytelling:", "Awkward:"),
  bold/caps emphasis, repeating the title field verbatim at the start of summary
• FORBIDDEN SUMMARY PATTERNS: "they discuss X" / "Conan and {name} explore" / "the segment covers"
• Low-energy episodes: find subtle dynamics, odd conversational textures, or unexpected sincerity
  — do not fabricate dramatic moments that did not occur
• Emotional/sincere moments: write them straight — do not deflect into comedy
• All 3-5 highlights together must be skimmable in under 15 seconds

General:
• fan_questions: [] in the vast majority of episodes — host-led is correct and expected
• quality_scores: 0-100 each. overall = 0.3×summary + 0.3×highlights + 0.2×questions + 0.2×responses
  Award 85+ to question_coverage when fan_questions=[] (correctly identifies host-led format)
• validation booleans: true only when the corresponding field is non-empty and meaningful
• Replace every PLACEHOLDER_UUID with a real UUID4 string

Respond with ONLY the JSON object. No prose. No markdown fences."""


def ask_claude_enrich(row, source_text):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("  [claude] ANTHROPIC_API_KEY not set")
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = ENRICH_PROMPT.format(
            title=row['title'],
            name=row['name'],
            location=row.get('location', ''),
            occupation=row.get('occupation', ''),
            topic=row.get('topic', ''),
            source_text=source_text[:8000],
        )
        msg = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=2500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = msg.content[0].text.strip()
        return extract_json_robust(raw)
    except Exception as e:
        print(f"  [claude] error: {e}")
        return None


# ── Validation ────────────────────────────────────────────────────────────────

# Known-bad phrases that indicate boilerplate generation
_BOILERPLATE_PATTERNS = [
    'as with all episodes in this format',
    'conan drives the interview, drawing',
    'the conversation explores',
    'they discuss',
]

def validate_result(r):
    """Return (ok, reason). Blocks empty/malformed/boilerplate extractions."""
    if not isinstance(r, dict):
        return False, 'not_a_dict'

    summary = r.get('summary', '')
    if not isinstance(summary, str) or len(summary) < 40:
        return False, f'summary_too_short ({len(summary) if isinstance(summary, str) else 0} chars)'

    # Reject if summary is still the placeholder text from the prompt
    if 'SEE FIELD RULES BELOW' in summary:
        return False, 'summary_is_placeholder'

    # Reject known boilerplate patterns
    summary_lower = summary.lower()
    for pat in _BOILERPLATE_PATTERNS:
        if pat in summary_lower:
            return False, f'summary_boilerplate ({pat!r})'

    hl = r.get('highlights_v2', [])
    if not isinstance(hl, list) or len(hl) < 3:
        return False, f'too_few_highlights_v2 ({len(hl) if isinstance(hl, list) else 0})'

    for h in hl:
        if not h.get('title') or not h.get('summary'):
            return False, 'highlight_missing_title_or_summary'
        # Reject highlights that still have the placeholder text
        if 'SEE FIELD RULES BELOW' in h.get('summary', ''):
            return False, 'highlight_is_placeholder'
        # Reject highlights whose summary just restates the title verbatim
        title_words = h['title'].lower().split()
        summ_start  = h['summary'].lower().split()[:len(title_words)]
        if len(title_words) >= 4 and title_words == summ_start:
            return False, f'highlight_title_echo ({h["title"][:40]!r})'

    qs = r.get('quality_scores', {})
    oq = qs.get('overall_quality', 0)
    if not isinstance(oq, (int, float)):
        return False, 'invalid_overall_quality'

    return True, 'ok'


# ── Upsert ────────────────────────────────────────────────────────────────────

SKIP_IF_VALID = {
    'highlights':      lambda v: isinstance(v, list) and len(v) >= 3,
    'fanQuestion':     lambda v: bool(v),
    'conanResponse':   lambda v: bool(v),
    'interactionType': lambda v: bool(v),
    'summary':         lambda v: isinstance(v, str) and len(v) > 100,
    'fan_questions':   lambda v: isinstance(v, list) and len(v) > 0,
    'highlights_v2':   lambda v: isinstance(v, list) and len(v) > 0,
    'episode_type':    lambda v: isinstance(v, dict) and 'fan_episode' in v,
    'quality_scores':  lambda v: isinstance(v, dict) and 'overall_quality' in v,
    'validation':      lambda v: isinstance(v, dict) and 'has_summary' in v,
}


def upsert_entry(entry, updates):
    """Apply field-level upsert. Returns list of field names that were written."""
    written = []
    for field, val in updates.items():
        checker = SKIP_IF_VALID.get(field)
        if checker and checker(entry.get(field)):
            continue  # already valid — don't overwrite
        entry[field] = val
        written.append(field)
    return written


def assign_real_uuids(result):
    """Replace placeholder UUID strings with real uuid4 values."""
    for q in result.get('fan_questions', []):
        q['question_id'] = str(uuid.uuid4())
    for h in result.get('highlights_v2', []):
        h['highlight_id'] = str(uuid.uuid4())


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('Conan Fan Map — Episode Enrichment Pipeline')
    print('=' * 60)
    if DRY_RUN:
        print('DRY RUN — no writes\n')

    with open(RICH_FILE, encoding='utf-8') as f:
        rich = json.load(f)
    with open(CSV_FILE, encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f))

    fan_rows = [r for r in all_rows if r['mustGo'].strip().lower() not in ('true', '1', 'yes')]
    print(f'Fan episodes: {len(fan_rows)}')

    # Determine which episodes need work
    to_process = []
    for row in fan_rows:
        title = row['title']
        name  = row['name']
        key   = f'{title}|{name}' if f'{title}|{name}' in rich else title
        entry = rich.get(key, {})

        # Skip if already enriched above min-quality threshold
        oq = (entry.get('quality_scores') or {}).get('overall_quality', 0)
        if oq >= MIN_QUALITY:
            continue
        # Skip if all three new fields already exist and are valid
        has_summary  = isinstance(entry.get('summary'), str) and len(entry.get('summary', '')) > 100
        has_v2hl     = isinstance(entry.get('highlights_v2'), list) and len(entry.get('highlights_v2', [])) >= 3
        has_ep_type  = isinstance(entry.get('episode_type'), dict)
        if has_summary and has_v2hl and has_ep_type:
            continue

        to_process.append((row, key, entry))

    print(f'Episodes needing enrichment: {len(to_process)}')
    if LIMIT:
        to_process = to_process[:LIMIT]
        print(f'Limited to: {len(to_process)}')
    print()

    log     = []
    success = 0
    failed  = 0

    for i, (row, key, entry) in enumerate(to_process):
        title = row['title']
        name  = row['name']
        occ   = row.get('occupation', '')
        print(f'[{i+1}/{len(to_process)}] {title} — {name} ({occ})')

        # 1. Fetch source text
        source_text = get_source_text(title, row.get('topic', ''))
        print(f'  source: {len(source_text)} chars')

        # 2. Extract via Claude
        result = ask_claude_enrich(row, source_text)
        if not result:
            print('  [skip] extraction returned nothing')
            failed += 1
            log.append({'key': key, 'title': title, 'status': 'failed',
                        'reason': 'extraction_returned_nothing', 'source_chars': len(source_text)})
            time.sleep(0.3)
            continue

        # 3. Validate
        ok, reason = validate_result(result)
        if not ok:
            print(f'  [skip] validation failed: {reason}')
            failed += 1
            log.append({'key': key, 'title': title, 'status': 'failed',
                        'reason': f'validation_{reason}', 'source_chars': len(source_text)})
            time.sleep(0.3)
            continue

        # 4. Assign real UUIDs
        assign_real_uuids(result)

        # 5. Set interactionType from fan_questions presence
        if not entry.get('interactionType'):
            result['interactionType'] = 'fan-led' if result.get('fan_questions') else 'host-led'

        # 6. Upsert into rich_data
        if key not in rich:
            rich[key] = {}
        entry = rich[key]

        updates = {k: v for k, v in result.items()
                   if k in ('summary', 'fan_questions', 'highlights_v2', 'episode_type',
                             'quality_scores', 'validation', 'interactionType')}
        written = upsert_entry(entry, updates)

        oq = (result.get('quality_scores') or {}).get('overall_quality', 0)
        status = 'success' if oq >= 70 else 'partial'
        print(f'  [{status}] quality={oq}  fields={written}')
        if result.get('highlights_v2'):
            for h in result['highlights_v2'][:2]:
                print(f'    [{h.get("category","?")}] {h.get("title","")[:70]}')

        log.append({
            'key': key, 'title': title, 'status': status,
            'quality_overall': oq, 'updated_fields': written,
            'source_chars': len(source_text), 'dry_run': DRY_RUN,
        })
        success += 1
        time.sleep(0.5)

    print()
    print(f'Results: {success} success, {failed} failed / {len(to_process)} total')

    if not DRY_RUN:
        with open(RICH_FILE, 'w', encoding='utf-8') as f:
            json.dump(rich, f, indent=2, ensure_ascii=False)
        print(f'Wrote {RICH_FILE}')
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        print(f'Wrote {LOG_FILE}')


if __name__ == '__main__':
    main()
