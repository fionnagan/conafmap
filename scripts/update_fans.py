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
RSS_URL   = 'https://feeds.simplecast.com/dHoohVNH'
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


# ── UUID audit ────────────────────────────────────────────────────────────────

def fetch_rss_uuids():
    """
    Fetch the Simplecast RSS feed and return a dict of {episode_title: uuid}.
    These are the canonical UUIDs for the Simplecast audio player.
    """
    import xml.etree.ElementTree as ET
    try:
        req = urllib.request.Request(
            RSS_URL,
            headers={'User-Agent': 'ConanFanMap/1.0 (github.com/fionnagan/conafmap)'}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            content = r.read().decode('utf-8')
        root = ET.fromstring(content)
        by_title = {}
        for item in root.iter('item'):
            title = (item.findtext('title') or '').strip()
            guid  = (item.findtext('guid') or '').strip()
            m = UUID_RE.search(guid)
            if title and m:
                by_title[title] = m.group()
        print(f"  RSS feed: {len(by_title)} episodes with UUIDs")
        return by_title
    except Exception as e:
        print(f"  [uuid-audit] Failed to fetch RSS: {e}")
        return {}


def audit_and_repair_uuids():
    """
    Compare UUIDs in episodes.csv against the live RSS feed.
    Overwrites any mismatched or empty UUIDs with the correct Simplecast UUID.
    Returns True if any rows were changed (so we know to commit).
    """
    print("\n[0] Auditing episode UUIDs against RSS feed…")
    rss_uuids = fetch_rss_uuids()
    if not rss_uuids:
        print("  Skipping UUID audit (RSS unavailable).")
        return False

    rows = []
    with open(CSV_FILE, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    fixed = 0
    for row in rows:
        title = row['title'].strip()
        rss_uuid = rss_uuids.get(title)
        if rss_uuid and row.get('uuid', '').strip() != rss_uuid:
            old = row.get('uuid', '') or '(empty)'
            row['uuid'] = rss_uuid
            fixed += 1
            print(f"  Fixed: '{title}'  {old[:8]}… → {rss_uuid[:8]}…")

    if fixed:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  ✓ Repaired {fixed} UUID(s) in episodes.csv")
    else:
        print(f"  ✓ All UUIDs look correct — no repairs needed")

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

    if not sources and desc:
        sources.append(f"--- RSS description ---\n{desc}")

    return '\n\n'.join(sources)


# ── Claude ────────────────────────────────────────────────────────────────────

def ask_claude(prompt, max_tokens=800):
    """Call Claude Haiku to extract structured info. Returns dict or None."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("    [claude] ANTHROPIC_API_KEY not set — skipping AI extraction")
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
        print(f"    [claude] API error: {e}")
    return None


def extract_fan_details(ep, source_text):
    """Extract name/location/occupation/topic from source text."""
    title = ep['title']

    # Must Go titles encode name + country directly
    if ep.get('is_must_go'):
        m = re.match(r'^conan must go:\s*(.+?)\s*\((.+?)\)\s*$', title, re.IGNORECASE)
        if m:
            return {
                'name':       m.group(1).strip(),
                'location':   m.group(2).strip(),
                'occupation': '???',
                'topic':      f"Conan visits {m.group(1).strip()} in {m.group(2).strip()}",
            }

    if not source_text:
        return {'name': '???', 'location': '???', 'occupation': '???', 'topic': '???'}

    prompt = f"""You are extracting fan details from a podcast episode of "Conan O'Brien Needs a Fan".

Episode title: {title}

Source text:
{source_text}

Extract the following four fields about the FAN CALLER (not Conan, not Sona, not Matt Gourley):
- name: their first name (or full name / stage name if better known by it)
- location: "City, ST" for US (2-letter state code), "City, Country" for international
- occupation: their job title as described on the show
- topic: one sentence (under 15 words) about what they discussed with Conan

Respond with ONLY a JSON object:
{{"name": "...", "location": "...", "occupation": "...", "topic": "..."}}

Use "???" for any field you cannot determine."""

    result = ask_claude(prompt)
    if result and isinstance(result, dict):
        out = {k: str(result.get(k, '???')).strip() or '???' for k in ('name', 'location', 'occupation', 'topic')}
        print(f"    [details] {out}")
        return out

    print(f"    [details] Claude returned nothing — using placeholders")
    return {'name': '???', 'location': '???', 'occupation': '???', 'topic': '???'}


def extract_qa_and_highlights(title, fan_name, source_text):
    """
    Extract fanQuestion, conanResponse, and 3 highlights from transcript.
    Returns dict ready to write into rich_data.json, or None if no source.
    """
    if not source_text:
        print(f"    [qa] No source text — skipping Q&A extraction")
        return None

    prompt = f"""You are extracting Q&A and highlights from a podcast episode of "Conan O'Brien Needs a Fan".

Episode title: {title}
Fan name: {fan_name}

Transcript / source text:
{source_text}

Extract:
1. fanQuestion — The specific question the fan asked Conan (verbatim or close paraphrase, 1 sentence)
2. conanResponse — How Conan responded to that question (2-3 sentences capturing his actual answer/reaction)
3. highlights — Exactly 3 short, funny/interesting highlights from the conversation (each under 20 words, written as entertaining observations)

Respond with ONLY a JSON object:
{{
  "fanQuestion": "...",
  "conanResponse": "...",
  "highlights": ["...", "...", "..."]
}}

If the transcript is too short or the question cannot be found, use empty strings and an empty array."""

    result = ask_claude(prompt, max_tokens=1000)
    if result and isinstance(result, dict):
        qa = {
            'fanQuestion':   str(result.get('fanQuestion', '')).strip(),
            'conanResponse': str(result.get('conanResponse', '')).strip(),
            'highlights':    [str(h).strip() for h in result.get('highlights', []) if str(h).strip()],
        }
        print(f"    [qa] fanQuestion: {qa['fanQuestion'][:80]}...")
        print(f"    [qa] highlights: {len(qa['highlights'])} extracted")
        return qa

    print(f"    [qa] Claude returned nothing for Q&A")
    return None


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
    for ep in candidates:
        print(f"\n  → {ep['title']}")

        # Fetch transcript once, reuse for both extractions
        source_text = get_source_text(ep['title'], ep.get('desc', ''))
        if source_text:
            print(f"    [source] {len(source_text)} chars of source text")
        else:
            print(f"    [source] no transcript found — using RSS description only")

        # Extract fan profile
        details = extract_fan_details(ep, source_text)

        # Extract Q&A + highlights → rich_data.json
        qa = extract_qa_and_highlights(ep['title'], details['name'], source_text)
        if qa and (qa['fanQuestion'] or qa['highlights']):
            rich_data[ep['title']] = qa
            rich_updated = True
            print(f"    [rich] Added Q&A for '{ep['title']}'")

        # Geocode location
        if details['location'] != '???':
            geocode(details['location'], geocache)

        row = {
            'date':       ep['date'],
            'uuid':       ep['uuid'],
            'mustGo':     'true' if ep.get('is_must_go') else 'false',
            'title':      ep['title'],
            'name':       details['name'],
            'location':   details['location'],
            'occupation': details['occupation'],
            'topic':      details['topic'],
        }
        new_rows.append(row)

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

    files_to_add = ['data/episodes.csv', 'data/geocache.json', 'dist/index.html']
    if rich_updated:
        files_to_add.append('data/rich_data.json')

    subprocess.run(['git', 'add'] + files_to_add, cwd=ROOT, check=True)
    subprocess.run(['git', 'commit', '-m', msg], cwd=ROOT, check=True)
    print(f"  Committed: \"{msg}\"")
    print("\n✓ Update complete. GitHub Actions will push the commit.")


if __name__ == '__main__':
    main()
