#!/usr/bin/env python3
"""
scripts/update_fans.py — Automated fan episode updater

Called by GitHub Actions every Monday and Thursday.

Flow:
  1. Run RSS scraper to find new episode candidates
  2. For each new episode, fetch transcript/show notes
  3. Ask Claude to extract: fan name, location, occupation, topic
  4. Geocode any new locations via Nominatim
  5. Append rows to data/episodes.csv
  6. Run build.py to rebuild dist/conan-fan-map.html
  7. Git commit the changes

Requires: ANTHROPIC_API_KEY env var (set as GitHub Actions secret)
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data'
CSV_FILE = DATA_DIR / 'episodes.csv'
GEO_FILE = DATA_DIR / 'geocache.json'

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


def geocode(location_str, cache):
    """Return [lat, lng] for a location string. Uses cache first, then Nominatim."""
    if location_str in cache:
        return cache[location_str]
    query = urllib.parse.quote(location_str)
    url   = f'https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1'
    try:
        import urllib.parse
        req = urllib.request.Request(
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


# ── Claude extraction ─────────────────────────────────────────────────────────

def ask_claude(prompt):
    """Call Claude claude-haiku-4-5 to extract structured info. Returns dict or None."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print("    [claude] ANTHROPIC_API_KEY not set — skipping AI extraction")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=512,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = msg.content[0].text.strip()
        # Expect JSON in the response
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"    [claude] API error: {e}")
    return None


def extract_fan_details(ep):
    """
    Try to extract name/location/occupation/topic for a new episode.
    Returns dict with those four keys (may contain '???' for unknowns).
    """
    title  = ep['title']
    desc   = ep.get('desc', '')
    slug   = make_slug(title)

    # Must Go titles encode the info: "Conan Must Go: Whitney (Thailand)"
    if ep.get('is_must_go'):
        m = re.match(r'^conan must go:\s*(.+?)\s*\((.+?)\)\s*$', title, re.IGNORECASE)
        if m:
            return {
                'name':       m.group(1).strip(),
                'location':   m.group(2).strip(),
                'occupation': '???',
                'topic':      f"Conan visits {m.group(1).strip()} in {m.group(2).strip()}",
            }

    # Fetch page text from multiple sources
    sources = []

    tc_url = f'https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes/{slug}'
    tc_text = fetch_url(tc_url)
    if tc_text and len(tc_text) > 500:
        # Strip HTML tags for a cleaner feed to Claude
        clean = re.sub(r'<[^>]+>', ' ', tc_text)
        clean = re.sub(r'\s+', ' ', clean)
        sources.append(f"--- TeamCoco page ({tc_url}) ---\n{clean[:3000]}")

    # HappyScribe transcript
    hs_url  = f'https://podcasts.happyscribe.com/conan-o-brien-needs-a-friend/{slug}'
    hs_text = fetch_url(hs_url)
    if hs_text and len(hs_text) > 500:
        clean2 = re.sub(r'<[^>]+>', ' ', hs_text)
        clean2 = re.sub(r'\s+', ' ', clean2)
        sources.append(f"--- HappyScribe transcript ({hs_url}) ---\n{clean2[:3000]}")

    if not sources and desc:
        sources.append(f"--- RSS description ---\n{desc}")

    if not sources:
        print(f"    [extract] No source text found for '{title}'")
        return {'name': '???', 'location': '???', 'occupation': '???', 'topic': '???'}

    context = '\n\n'.join(sources)

    prompt = f"""You are extracting fan details from a podcast episode of "Conan O'Brien Needs a Fan".

Episode title: {title}

Source text:
{context}

Extract the following four fields about the FAN CALLER (not Conan, not Sona, not Matt):
- name: their first name (or full name if given)
- location: "City, ST" for US cities (2-letter state code), "City, Country" for international (e.g. "Toronto, Canada", "London, UK")
- occupation: their job title as they described it on the show
- topic: one short sentence (under 15 words) about what they discussed with Conan

Respond with ONLY a JSON object, no explanation:
{{"name": "...", "location": "...", "occupation": "...", "topic": "..."}}

If a field cannot be determined from the text, use "???" as the value."""

    result = ask_claude(prompt)
    if result and isinstance(result, dict):
        # Validate keys
        out = {}
        for k in ('name', 'location', 'occupation', 'topic'):
            out[k] = str(result.get(k, '???')).strip() or '???'
        print(f"    [claude] extracted: {out}")
        return out

    print(f"    [extract] Claude returned nothing useful for '{title}'")
    return {'name': '???', 'location': '???', 'occupation': '???', 'topic': '???'}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Conan Fan Map — Episode Updater")
    print("=" * 60)

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
        print("  No new episodes found. Nothing to do.")
        return

    print(f"  Found {len(candidates)} new candidate(s):")
    for ep in candidates:
        flag = ' [MUST GO]' if ep.get('is_must_go') else ''
        print(f"  • {ep['date']}  {ep['title']}{flag}")

    # 2. Load geocache
    geocache = load_geocache()
    new_rows = []

    # 3. Extract details + geocode each new episode
    print("\n[2] Extracting fan details…")
    for ep in candidates:
        print(f"\n  → {ep['title']}")
        details = extract_fan_details(ep)

        # Geocode if we got a real location
        if details['location'] != '???':
            import urllib.parse
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
        print(f"    Row: {row}")

    # 4. Append to episodes.csv
    print(f"\n[3] Appending {len(new_rows)} row(s) to episodes.csv…")
    fieldnames = ['date', 'uuid', 'mustGo', 'title', 'name', 'location', 'occupation', 'topic']
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for row in new_rows:
            writer.writerow(row)
    print("  Done.")

    # 5. Save updated geocache
    save_geocache(geocache)

    # 6. Rebuild
    print("\n[4] Rebuilding site…")
    result = subprocess.run(['python3', 'build.py'], capture_output=True, text=True, cwd=ROOT)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"BUILD FAILED:\n{result.stderr}")
        sys.exit(1)

    # 7. Git commit
    print("\n[5] Committing changes…")
    names  = ', '.join(r['name'] for r in new_rows)
    date   = new_rows[-1]['date'] if new_rows else 'unknown'
    msg    = f"Add {len(new_rows)} new fan(s): {names} ({date})"

    subprocess.run(['git', 'add',
                    'data/episodes.csv',
                    'data/geocache.json',
                    'dist/conan-fan-map.html'],
                   cwd=ROOT, check=True)
    subprocess.run(['git', 'commit', '-m', msg], cwd=ROOT, check=True)
    print(f"  Committed: \"{msg}\"")
    print("\n✓ Update complete. GitHub Actions will push the commit.")


if __name__ == '__main__':
    import urllib.parse   # ensure available for geocode()
    main()
