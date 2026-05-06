#!/usr/bin/env python3
"""
backfill_rich_data.py — Backfill highlights + Q&A for all fan episodes.

For each episode that is missing highlights or Q&A attribution:
  1. Fetch source text (TeamCoco page, HappyScribe, RSS description)
  2. Call Claude to extract highlights (≥3) + Q&A with correct speaker attribution
  3. Field-level upsert: never overwrite valid existing data
  4. Write results to rich_data.json

Run:  python3 scripts/backfill_rich_data.py [--dry-run] [--limit N]
"""

import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT      = Path(__file__).parent.parent
DATA_DIR  = ROOT / 'data'
CSV_FILE  = DATA_DIR / 'episodes.csv'
RICH_FILE = DATA_DIR / 'rich_data.json'
LOG_FILE  = DATA_DIR / 'backfill_log.json'

DRY_RUN = '--dry-run' in sys.argv
LIMIT   = None
for i, a in enumerate(sys.argv):
    if a == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])


# ── Helpers (shared logic with update_fans.py) ────────────────────────────────

def fetch_url(url, timeout=10):
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'ConanFanMap/1.0 (+github.com/fionnagan/conafmap)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        return ''


def make_slug(title):
    s = title.lower()
    s = re.sub(r"[''']", '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def get_source_text(title, desc=''):
    """Fetch TeamCoco page + HappyScribe transcript + RSS description."""
    slug    = make_slug(title)
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

    # Always include RSS description
    if desc and len(desc.strip()) > 20:
        desc_clean = re.sub(r'<[^>]+>', ' ', desc)
        desc_clean = re.sub(r'\s+', ' ', desc_clean).strip()
        sources.append(f"--- RSS description ---\n{desc_clean[:1000]}")

    return '\n\n'.join(sources)


def ask_claude(prompt, max_tokens=1200):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("  [claude] ANTHROPIC_API_KEY not set")
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=max_tokens,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = msg.content[0].text.strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"  [claude] error: {e}")
    return None


# ── Extraction ────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are extracting structured metadata from a "Conan O'Brien Needs a Fan" podcast episode.
In this segment, a fan calls in to talk WITH Conan. Conan interviews them about their unusual job/hobby/situation.

Episode title: {title}
Fan name: {name}
Fan occupation: {occupation}
Fan topic: {topic}

Source text:
{source_text}

── SPEAKER ATTRIBUTION RULES ──
Conan always asks the fan about THEIR life. The fan almost never quizzes Conan.
- fanQuestion = ONLY a question the FAN directed AT CONAN personally (e.g. "Have you ever been to Mumbai?")
- If the question is about the fan's own expertise/experience → Conan asked it → fanQuestion = ""
- When in doubt → fanQuestion = "" (the most common case is no fan question)
- interactionType = "fan-led" only if fanQuestion is non-empty; otherwise "host-led"
- If Conan asked a memorable question to the fan, put it in highlights as: "Conan asks fan: '[exact question]'"

── HIGHLIGHTS RULES ──
- Exactly 3 highlights, each ≤20 words
- Each must be specific and concrete — name the person, action, or punchline
- Derive directly from the source text — no invention beyond what's stated
- If source is thin (only RSS description), write 3 informative highlights about what the episode is about
- Avoid generic phrases like "they joke around" or "a fun conversation"
- If Conan asked a notable question, include it as one highlight: "Conan asks fan: '[question]'"

Respond with ONLY valid JSON:
{{
  "fanQuestion": "",
  "conanResponse": "",
  "interactionType": "host-led",
  "highlights": ["...", "...", "..."]
}}"""

METADATA_PROMPT = """You are writing 3 highlights for a "Conan O'Brien Needs a Fan" podcast episode.
You have limited source text, so write informative highlights based on what's known.

Episode title: {title}
Fan name: {name}
Fan occupation: {occupation}
Fan topic: {topic}

Write exactly 3 highlights, each ≤20 words, specific to this fan and their story.
Focus on what makes this fan/episode interesting — their unusual job, their situation, the angle of the conversation.
Do NOT write generic filler. Each highlight should tell us something real about this episode.

Respond with ONLY valid JSON:
{{
  "highlights": ["...", "...", "..."]
}}"""


def extract_for_episode(row, entry, desc=''):
    """
    Fetch source + call Claude. Returns dict of fields to upsert, or None.
    entry = existing rich_data entry (may be None or partial).
    """
    title      = row['title']
    name       = row['name']
    occupation = row['occupation']
    topic      = row.get('topic', '')

    already_has_hl = entry and len(entry.get('highlights', [])) >= 3
    already_has_qa = entry and entry.get('interactionType', '')

    source_text = get_source_text(title, desc)
    source_len  = len(source_text)
    print(f"    source: {source_len} chars")

    result = {}

    if source_len < 100:
        # No useful source — generate metadata-only highlights
        print(f"    [thin] using metadata-only prompt")
        prompt = METADATA_PROMPT.format(
            title=title, name=name, occupation=occupation, topic=topic
        )
        r = ask_claude(prompt, max_tokens=600)
        if r and isinstance(r, dict):
            hl = [h.strip() for h in r.get('highlights', []) if h.strip()]
            if len(hl) >= 3:
                result['highlights']      = hl[:3]
                result['interactionType'] = entry.get('interactionType', 'host-led') if entry else 'host-led'
                result['extraction_status'] = 'partial'
        return result if result else None

    # Full extraction
    prompt = EXTRACTION_PROMPT.format(
        title=title, name=name, occupation=occupation, topic=topic,
        source_text=source_text[:8000]
    )
    r = ask_claude(prompt, max_tokens=1200)
    if not r or not isinstance(r, dict):
        return None

    hl = [h.strip() for h in r.get('highlights', []) if h.strip()]
    fq = str(r.get('fanQuestion', '')).strip()
    cr = str(r.get('conanResponse', '')).strip()
    it = str(r.get('interactionType', 'host-led')).strip()

    if not already_has_hl and len(hl) >= 3:
        result['highlights'] = hl[:4]  # allow up to 4

    if not already_has_qa:
        result['fanQuestion']     = fq
        result['conanResponse']   = cr
        result['interactionType'] = it

    result['extraction_status'] = 'success' if len(result.get('highlights', entry.get('highlights',[]))) >= 3 else 'partial'
    return result if result else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Conan Fan Map — Rich Data Backfill")
    print("=" * 60)
    if DRY_RUN:
        print("DRY RUN — no writes\n")

    # Load data
    with open(RICH_FILE, encoding='utf-8') as f:
        rich = json.load(f)
    with open(CSV_FILE, encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f))

    # Filter to fan (non-Must Go) episodes
    fan_rows = [r for r in all_rows if r['mustGo'].strip().lower() not in ('true','1','yes')]
    print(f"Fan episodes: {len(fan_rows)}")

    # Identify which need work
    to_process = []
    for row in fan_rows:
        title = row['title']
        name  = row['name']
        key   = f"{title}|{name}" if f"{title}|{name}" in rich else title
        entry = rich.get(key)
        hl    = entry.get('highlights', []) if entry else []
        it    = entry.get('interactionType', '') if entry else ''
        needs_hl = len(hl) < 3
        needs_qa = not it
        if needs_hl or needs_qa:
            to_process.append((row, key, entry))

    print(f"Needing work: {len(to_process)}")
    if LIMIT:
        to_process = to_process[:LIMIT]
        print(f"Limited to: {len(to_process)}")
    print()

    log = []
    updated = 0
    failed  = 0

    for i, (row, key, entry) in enumerate(to_process):
        title = row['title']
        name  = row['name']
        occ   = row['occupation']
        print(f"[{i+1}/{len(to_process)}] {title} — {name} ({occ})")

        prev_state = {
            'highlights':      (entry or {}).get('highlights', []),
            'fanQuestion':     (entry or {}).get('fanQuestion', ''),
            'interactionType': (entry or {}).get('interactionType', ''),
        }

        updates = extract_for_episode(row, entry)

        if not updates:
            print(f"    [skip] extraction returned nothing")
            failed += 1
            log.append({'title': title, 'key': key, 'status': 'failed',
                        'reason': 'extraction_returned_nothing', 'prev': prev_state})
            time.sleep(0.3)
            continue

        hl = updates.get('highlights', [])
        if hl and len(hl) < 3:
            print(f"    [skip] only {len(hl)} highlights — need ≥3")
            failed += 1
            log.append({'title': title, 'key': key, 'status': 'failed',
                        'reason': f'only_{len(hl)}_highlights', 'prev': prev_state})
            time.sleep(0.3)
            continue

        # Field-level upsert
        if entry is None:
            rich[key] = {}
            entry = rich[key]
        elif key not in rich:
            rich[key] = entry

        updated_fields = []
        for field, val in updates.items():
            if field == 'extraction_status':
                continue
            # Only write if field is currently empty/missing
            current = entry.get(field)
            if field == 'highlights':
                if not current or len(current) < 3:
                    entry[field] = val
                    updated_fields.append(field)
            else:
                if not current:
                    entry[field] = val
                    updated_fields.append(field)

        status = updates.get('extraction_status', 'success')
        print(f"    [{status}] updated: {updated_fields}")
        if hl:
            for h in hl[:3]:
                print(f"      • {h[:80]}")

        log.append({'title': title, 'key': key, 'status': status,
                    'updated_fields': updated_fields, 'prev': prev_state,
                    'new': {f: entry.get(f) for f in updated_fields}})
        updated += 1
        time.sleep(0.5)  # gentle rate limit on Claude API

    print()
    print(f"Results: {updated} updated, {failed} failed / {len(to_process)} total")

    if not DRY_RUN:
        with open(RICH_FILE, 'w', encoding='utf-8') as f:
            json.dump(rich, f, indent=2, ensure_ascii=False)
        print(f"Wrote {RICH_FILE}")

        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        print(f"Wrote {LOG_FILE}")


if __name__ == '__main__':
    main()
