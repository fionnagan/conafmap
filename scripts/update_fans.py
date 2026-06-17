#!/usr/bin/env python3
"""
scripts/update_fans.py — Automated fan episode updater

Called by GitHub Actions every Monday and Thursday.

Flow:
  1. Audit & repair UUIDs in episodes.csv against live RSS feed
  2. Run RSS scraper to find new episode candidates
  3. For each new episode, fetch transcript/show notes
  4. Ask Claude to extract: fan name, location, occupation, topic
  5. Ask Claude to extract: fanQuestion, conanResponse, highlights → rich_data.json
  6. Geocode any new locations via Nominatim
  7. Append rows to data/episodes.csv
  8. Run build.py to rebuild dist/index.html
  9. Git commit the changes

Requires: ANTHROPIC_API_KEY env var (set as GitHub Actions secret)
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT      = Path(__file__).parent.parent
DATA_DIR  = ROOT / 'data'
CSV_FILE  = DATA_DIR / 'episodes.csv'
GEO_FILE  = DATA_DIR / 'geocache.json'
RICH_FILE = DATA_DIR / 'rich_data.json'
UUID_RE   = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_url(url, timeout=15):
    """Fetch a URL, return text or '' on error."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'ConanFanMap/1.0 (github.com/fionnagan/conafmap)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"    [fetch] {url[:80]} → {e}")
        return ''


def make_slug(title):
    """Convert episode title to URL slug (matches build.py logic)."""
    s = title.lower()
    s = re.sub(r"[^\w\s-]", '', s)
    s = re.sub(r'\s+', '-', s.strip())
    return s


def load_geocache():
    if GEO_FILE.exists():
        with open(GEO_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_geocache(cache):
    with open(GEO_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def load_rich_data():
    if RICH_FILE.exists():
        with open(RICH_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_rich_data(data):
    with open(RICH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def geocode(location_str, cache):
    """Return [lat, lng] for a location string. Uses cache first, then Nominatim."""
    if location_str in cache:
        return cache[location_str]
    try:
        query = urllib.parse.quote(location_str)
        url   = f'https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1'
        req   = urllib.request.Request(
            url,
            headers={'User-Agent': 'ConanFanMap/1.0 (github.com/fionnagan/conafmap)'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read())
        if results:
            coords = [float(results[0]['lat']), float(results[0]['lon'])]
            cache[location_str] = coords
            print(f"    [geocode] {location_str} → {coords}")
            time.sleep(1)   # Nominatim rate limit: 1 req/sec
            return coords
    except Exception as e:
        print(f"    [geocode] failed for '{location_str}': {e}")
    return None


# ── UUID helpers ──────────────────────────────────────────────────────────────

SIMPLECAST_PODCAST = 'conan-obrien-needs-a-friend'

def episode_slug(title):
    """Convert episode title to Simplecast URL slug."""
    s = title.lower()
    s = re.sub(r"[''']", '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def get_player_uuid(title):
    """
    Fetch the real Simplecast player UUID for an episode via the public oEmbed API.
    The RSS <guid> UUID is NOT the player UUID — oEmbed is the authoritative source.
    Returns the UUID string, or '' on failure.
    """
    slug = episode_slug(title)
    url = (f'https://api.simplecast.com/oembed'
           f'?url=https://{SIMPLECAST_PODCAST}.simplecast.com/episodes/{slug}')
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'ConanFanMap/1.0 (github.com/fionnagan/conafmap)',
                     'Accept': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        html = data.get('html', '')
        m = UUID_RE.search(html)
        return m.group() if m else ''
    except Exception:
        return ''


def audit_and_repair_uuids():
    """
    Find any episodes.csv rows with empty UUIDs and fill them via oEmbed.
    (We no longer compare against RSS GUIDs — those are different UUIDs.)
    Returns True if any rows were changed.
    """
    print("\n[0] Auditing episode UUIDs (oEmbed repair for empty entries)…")

    rows = []
    with open(CSV_FILE, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    empty_rows = [r for r in rows if not r.get('uuid', '').strip()]
    if not empty_rows:
        print("  ✓ No empty UUIDs — nothing to repair")
        return False

    print(f"  Found {len(empty_rows)} empty UUID(s), fetching via oEmbed…")
    fixed = 0
    for row in empty_rows:
        uuid = get_player_uuid(row['title'])
        if uuid:
            row['uuid'] = uuid
            fixed += 1
            print(f"  ✓ '{row['title']}' → {uuid}")
        else:
            print(f"  - '{row['title']}' → not on Simplecast (HBO-only or unavailable)")
        time.sleep(0.3)

    if fixed:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  ✓ Filled {fixed} UUID(s)")

    return fixed > 0


# ── Source text fetching ──────────────────────────────────────────────────────

def get_source_text(title, desc=''):
    """
    Fetch all available source text for an episode: TeamCoco page + HappyScribe transcript.
    Returns a single combined string (may be empty if nothing found).
    """
    slug    = make_slug(title)
    sources = []

    tc_url  = f'https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes/{slug}'
    tc_text = fetch_url(tc_url)
    if tc_text and len(tc_text) > 500:
        clean = re.sub(r'<[^>]+>', ' ', tc_text)
        clean = re.sub(r'\s+', ' ', clean)
        sources.append(f"--- TeamCoco page ---\n{clean[:4000]}")

    hs_url  = f'https://podcasts.happyscribe.com/conan-o-brien-needs-a-friend/{slug}'
    hs_text = fetch_url(hs_url)
    if hs_text and len(hs_text) > 500:
        clean2 = re.sub(r'<[^>]+>', ' ', hs_text)
        clean2 = re.sub(r'\s+', ' ', clean2)
        sources.append(f"--- HappyScribe transcript ---\n{clean2[:6000]}")

    # Always include RSS description — it's often the most reliable source
    # for fan name/location even when richer pages are available
    if desc:
        sources.append(f"--- RSS description ---\n{desc}")

    return '\n\n'.join(sources)


# ── Extraction tool definition ────────────────────────────────────────────────

EXTRACT_TOOL = {
    "name": "record_fan_episode",
    "description": (
        "Record all structured data extracted from a 'Conan O'Brien Needs a Fan' episode. "
        "Call this once with all fields populated after analyzing the source text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Fan's first name, or full name if better known by it. Not Conan, Sona, or Matt Gourley."
            },
            "location": {
                "type": "string",
                "description": "'City, ST' for US cities (2-letter state code), 'City, Country' for international. Example: 'Austin, TX' or 'Sydney, Australia'."
            },
            "occupation": {
                "type": "string",
                "description": "Fan's job title as described on the show."
            },
            "topic": {
                "type": "string",
                "description": "One sentence under 15 words about what the fan discussed with Conan."
            },
            "fan_question": {
                "type": "string",
                "description": "A question the fan explicitly directed AT Conan personally. Empty string if the fan didn't ask Conan anything — this is the most common case. Do NOT include questions Conan asked the fan."
            },
            "conan_response": {
                "type": "string",
                "description": "Conan's response to the fan's question. Empty string if fan_question is empty."
            },
            "interaction_type": {
                "type": "string",
                "enum": ["fan-led", "host-led"],
                "description": "'fan-led' if the fan asked Conan a personal question; 'host-led' if Conan drove all the questions (most common)."
            },
            "highlights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 3 short highlights from the conversation, each under 20 words. If Conan asked a memorable or funny question, include it as: \"Conan asks: '[exact question]'\". Empty array if the transcript is too short."
            }
        },
        "required": ["name", "location", "occupation", "topic", "fan_question", "conan_response", "interaction_type", "highlights"]
    }
}


# ── Extraction ────────────────────────────────────────────────────────────────

def extract_episode_data(ep, source_text):
    """
    Single tool-use call to extract all fan data from source text.
    Returns a dict with keys: name, location, occupation, topic,
    fan_question, conan_response, interaction_type, highlights.
    Returns None if extraction fails or required fields are empty.
    """
    title = ep['title']

    # Must Go titles encode name + country in the title — occupation requires
    # manual entry, so we return ??? and let the ??? guard skip it.
    if ep.get('is_must_go'):
        m = re.match(r'^conan must go:\s*(.+?)\s*\((.+?)\)\s*$', title, re.IGNORECASE)
        if m:
            return {
                'name':             m.group(1).strip(),
                'location':         m.group(2).strip(),
                'occupation':       '???',
                'topic':            f"Conan visits {m.group(1).strip()} in {m.group(2).strip()}",
                'fan_question':     '',
                'conan_response':   '',
                'interaction_type': 'host-led',
                'highlights':       [],
            }

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("    [claude] ANTHROPIC_API_KEY not set — skipping extraction")
        return None

    if not source_text:
        print("    [extract] No source text — skipping")
        return None

    prompt = f"""You are extracting structured data from a "Conan O'Brien Needs a Fan" podcast episode.

Episode title: {title}

Source text:
{source_text}

IMPORTANT — SPEAKER ROLES:
- This is a segment where a fan CALLS IN and Conan interviews them.
- The fan almost never asks Conan a question. Conan does most of the asking.
- fan_question MUST be a question the FAN directed AT CONAN personally.
- If Conan asked the fan questions (the normal case), that is NOT a fan_question.

Call the record_fan_episode tool with all fields populated."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=1200,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "any"},
            messages=[{'role': 'user', 'content': prompt}]
        )
    except Exception as e:
        print(f"    [claude] API error: {e}")
        return None

    tool_input = None
    for block in msg.content:
        if block.type == 'tool_use' and block.name == 'record_fan_episode':
            tool_input = block.input
            break

    if not tool_input:
        print("    [extract] Claude did not call the tool")
        return None

    # Reject if any visible field is empty — same quality bar as the old ??? guard
    missing = [k for k in ('name', 'location', 'occupation') if not str(tool_input.get(k, '')).strip()]
    if missing:
        print(f"    [extract] Missing required field(s): {missing}")
        return None

    result = {
        'name':             str(tool_input.get('name', '')).strip(),
        'location':         str(tool_input.get('location', '')).strip(),
        'occupation':       str(tool_input.get('occupation', '')).strip(),
        'topic':            str(tool_input.get('topic', '')).strip() or '???',
        'fan_question':     str(tool_input.get('fan_question', '')).strip(),
        'conan_response':   str(tool_input.get('conan_response', '')).strip(),
        'interaction_type': str(tool_input.get('interaction_type', 'host-led')).strip(),
        'highlights':       [str(h).strip() for h in tool_input.get('highlights', []) if str(h).strip()],
    }

    print(f"    [extract] {result['name']} — {result['location']} — {result['occupation']}")
    interaction = result['interaction_type']
    fan_q_preview = result['fan_question'][:60] if result['fan_question'] else '(none — host-led)'
    print(f"    [extract] interactionType: {interaction} | fanQuestion: {fan_q_preview}")
    print(f"    [extract] highlights: {len(result['highlights'])} extracted")
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Conan Fan Map — Episode Updater")
    print("=" * 60)

    # 0. Audit + repair UUIDs (runs every time, catches drift)
    uuids_repaired = audit_and_repair_uuids()

    # 1. Detect new episodes
    print("\n[1] Checking RSS feed for new episodes…")
    try:
        result = subprocess.run(
            ['python3', 'lib/scraper.py', '--json'],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode != 0:
            print(f"Scraper error:\n{result.stderr}")
            sys.exit(1)
        candidates = json.loads(result.stdout.strip() or '[]')
    except Exception as e:
        print(f"Failed to run scraper: {e}")
        sys.exit(1)

    if not candidates:
        if uuids_repaired:
            print("  No new episodes, but UUIDs were repaired — rebuilding + committing.")
            result = subprocess.run(['python3', 'build.py'], capture_output=True, text=True, cwd=ROOT)
            print(result.stdout.strip())
            if result.returncode != 0:
                print(f"BUILD FAILED:\n{result.stderr}")
                sys.exit(1)
            subprocess.run(['git', 'add', 'data/episodes.csv', 'dist/index.html'], cwd=ROOT, check=True)
            subprocess.run(['git', 'commit', '-m', 'Fix Simplecast UUIDs (audio player repair)'], cwd=ROOT, check=True)
            print("\n✓ UUID repair committed. GitHub Actions will push.")
        else:
            print("  No new episodes found. Nothing to do.")
        return

    print(f"  Found {len(candidates)} new candidate(s):")
    for ep in candidates:
        flag = ' [MUST GO]' if ep.get('is_must_go') else ''
        print(f"  • {ep['date']}  {ep['title']}{flag}")

    # 2. Load data files (reload CSV in case UUIDs were repaired above)
    geocache  = load_geocache()
    rich_data = load_rich_data()
    new_rows  = []
    rich_updated = False

    # 3. Process each new episode
    print("\n[2] Extracting fan details + Q&A…")
    skipped = []
    for ep in candidates:
        print(f"\n  → {ep['title']}")

        # Fetch transcript once, reuse for both extractions
        source_text = get_source_text(ep['title'], ep.get('desc', ''))
        if source_text:
            print(f"    [source] {len(source_text)} chars of source text")
        else:
            print(f"    [source] no transcript found — using RSS description only")

        # Single call extracts profile + Q&A + highlights together
        data = extract_episode_data(ep, source_text)

        if data is None:
            print(f"    [skip] Extraction failed — skipping '{ep['title']}'.")
            print(f"    [skip] RSS desc: {ep.get('desc','')[:120]}")
            skipped.append(ep['title'])
            continue

        details = {k: data[k] for k in ('name', 'location', 'occupation', 'topic')}

        # Guard: never commit entries with empty required fields
        missing = [k for k in ('name', 'location', 'occupation') if not details[k] or details[k] == '???']
        if missing:
            print(f"    [skip] Unknown field(s): {missing} — skipping '{ep['title']}'.")
            print(f"    [skip] RSS desc: {ep.get('desc','')[:120]}")
            skipped.append(ep['title'])
            continue

        qa = {
            'fanQuestion':     data['fan_question'],
            'conanResponse':   data['conan_response'],
            'interactionType': data['interaction_type'],
            'highlights':      data['highlights'],
        }
        if qa['fanQuestion'] or qa['highlights']:
            rich_data[ep['title']] = qa
            rich_updated = True
            print(f"    [rich] Added Q&A for '{ep['title']}'")

        # Geocode location
        if details['location'] and details['location'] != '???':
            geocode(details['location'], geocache)

        # Get real Simplecast player UUID via oEmbed (RSS guid is a different UUID)
        player_uuid = get_player_uuid(ep['title'])
        if player_uuid:
            print(f"    [uuid] {player_uuid}")
        else:
            print(f"    [uuid] not found via oEmbed (HBO-only or not yet published)")

        row = {
            'date':       ep['date'],
            'uuid':       player_uuid,
            'mustGo':     'true' if ep.get('is_must_go') else 'false',
            'title':      ep['title'],
            'name':       details['name'],
            'location':   details['location'],
            'occupation': details['occupation'],
            'topic':      details['topic'],
        }
        new_rows.append(row)

    if skipped:
        print(f"\n  ⚠ Skipped {len(skipped)} non-fan/unextractable episode(s): {', '.join(skipped)}")

    if not new_rows:
        print("\n  No valid fan episodes to add after filtering. Done.")
        return

    # 4. Append to episodes.csv
    print(f"\n[3] Appending {len(new_rows)} row(s) to episodes.csv…")
    fieldnames = ['date', 'uuid', 'mustGo', 'title', 'name', 'location', 'occupation', 'topic']
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for row in new_rows:
            writer.writerow(row)

    # 5. Save geocache + rich_data
    save_geocache(geocache)
    if rich_updated:
        save_rich_data(rich_data)
        print(f"  Saved updated rich_data.json")

    # 5b. Full structured enrichment (summary + highlights_v2) for new episodes
    if new_rows:
        titles_arg = ','.join(r['title'] for r in new_rows)
        print(f"\n[3b] Full enrichment for new episode(s): {titles_arg}")
        er = subprocess.run(
            ['python3', 'scripts/enrich_episodes.py', '--titles', titles_arg],
            capture_output=True, text=True, cwd=ROOT,
        )
        if er.stdout:
            print(er.stdout.rstrip())
        if er.returncode != 0:
            print(f"  [enrich] warning (exit {er.returncode}):\n{er.stderr[:800]}")
        else:
            rich_updated = True

    # 6. Rebuild
    print("\n[4] Rebuilding site…")
    result = subprocess.run(['python3', 'build.py'], capture_output=True, text=True, cwd=ROOT)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"BUILD FAILED:\n{result.stderr}")
        sys.exit(1)

    # 7. Git commit
    print("\n[5] Committing changes…")
    names = ', '.join(r['name'] for r in new_rows)
    date  = new_rows[-1]['date'] if new_rows else 'unknown'
    msg   = f"Add {len(new_rows)} new fan(s): {names} ({date})"

    files_to_add = ['data/episodes.csv', 'data/geocache.json', 'dist/index.html', 'dist/.build_ts']
    if rich_updated:
        files_to_add.extend(['data/rich_data.json', 'data/enrich_log.json'])

    subprocess.run(['git', 'add'] + files_to_add, cwd=ROOT, check=True)
    subprocess.run(['git', 'commit', '-m', msg], cwd=ROOT, check=True)
    print(f"  Committed: \"{msg}\"")
    print("\n✓ Update complete. GitHub Actions will push the commit.")


if __name__ == '__main__':
    main()
