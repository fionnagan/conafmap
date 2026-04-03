"""
lib/scraper.py — Simplecast RSS monitor for new Conan fan episodes

Usage:
  python lib/scraper.py              # check for new episodes, print candidates
  python lib/scraper.py --json       # output as JSON
  python lib/scraper.py --append     # append confirmed fan episodes to episodes.csv

What it does:
  1. Fetches the Simplecast RSS feed for "Conan O'Brien Needs a Friend"
  2. Parses episode titles and GUIDs
  3. Cross-references against existing episodes.csv UUIDs
  4. Identifies episodes likely to be fan segments (title heuristics)
  5. Outputs new candidate rows ready for episodes.csv

Fan episode title patterns (all confirmed from data):
  - "Conan Must Go: <Name> (<Country>)"
  - Anything else is a potential fan episode if it's under ~60 chars and not
    a "Best Of", interview-only, or known non-fan format.

NOTE: The scraper can only detect NEW episode UUIDs. You still need to manually
verify name/location/occupation from listening to the episode or checking the
transcript. The scraper outputs placeholder rows for you to fill in.
"""

import csv
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT       = Path(__file__).parent.parent
DATA_DIR   = ROOT / 'data'
CSV_FILE   = DATA_DIR / 'episodes.csv'
RSS_URL    = 'https://feeds.simplecast.com/dHoohVNH'

# Simplecast UUID regex (appears in enclosure URLs and GUIDs)
UUID_RE    = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

# Episode title patterns that are clearly NOT fan episodes
NON_FAN_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^best of\b',
        r'\bbest of\b',
        r'\binterview\b',
        r'\bconan obrien needs a friend\b',   # generic title episodes
        r'\breturns\b',             # "Lisa Kudrow Returns Again"
        r'^staff (review|picks)\b', # "Staff Review With…"
        r'^[A-Z][a-z]+ [A-Z][a-z]+$',  # "First Last" celebrity name format
        r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
    ]
]

# Title patterns that ARE likely fan episodes (positive signals)
FAN_SIGNALS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^conan must go:',
        r"needs a fan",
    ]
]


def load_existing_data():
    """Return (set of UUIDs, latest date string) from episodes.csv."""
    uuids   = set()
    max_date = '2000-01-01'
    if not CSV_FILE.exists():
        return uuids, max_date
    with open(CSV_FILE, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            uid  = row.get('uuid', '').strip()
            date = row.get('date', '').strip()
            if uid:
                uuids.add(uid)
            if date > max_date:
                max_date = date
    return uuids, max_date


def fetch_feed(url=RSS_URL):
    """Fetch and parse the Simplecast RSS feed. Returns list of episode dicts."""
    req = urllib.request.Request(url, headers={'User-Agent': 'ConanFanMap/1.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)
    ns   = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}
    episodes = []

    for item in root.iter('item'):
        title   = (item.findtext('title') or '').strip()
        pub_raw = (item.findtext('pubDate') or '').strip()
        guid    = (item.findtext('guid') or '').strip()
        desc    = (item.findtext('description') or '').strip()

        # Extract Simplecast UUID from GUID or enclosure URL
        uuid = ''
        m = UUID_RE.search(guid)
        if m:
            uuid = m.group()
        else:
            enc = item.find('enclosure')
            if enc is not None:
                url_attr = enc.get('url', '')
                m2 = UUID_RE.search(url_attr)
                if m2:
                    uuid = m2.group()

        # Parse date → ISO format
        date = ''
        if pub_raw:
            try:
                dt   = datetime.strptime(pub_raw[:25].strip(), '%a, %d %b %Y %H:%M:%S')
                date = dt.strftime('%Y-%m-%d')
            except ValueError:
                pass

        episodes.append({
            'title':  title,
            'uuid':   uuid,
            'date':   date,
            'desc':   desc[:300],
        })

    return episodes


def is_likely_fan_episode(title):
    """
    Return True if the title looks like it could be a fan episode.
    Must Go titles are always fans. Generic-sounding short titles are candidates.
    """
    if any(p.search(title) for p in FAN_SIGNALS):
        return True
    if any(p.search(title) for p in NON_FAN_PATTERNS):
        return False
    # Short titles with no obvious non-fan markers are possible fan episodes
    if len(title) < 70:
        return True
    return False


def find_new_episodes(verbose=True):
    """
    Fetch RSS, compare with episodes.csv, return list of new candidate episodes.
    Only considers episodes published AFTER the latest date in episodes.csv.
    Each item has: title, uuid, date, desc, is_must_go
    """
    existing, latest_date = load_existing_data()

    if verbose:
        print(f'  Loaded {len(existing)} existing UUIDs from episodes.csv (latest: {latest_date})')
        print(f'  Fetching RSS feed…')

    all_eps = fetch_feed()

    if verbose:
        print(f'  RSS returned {len(all_eps)} episodes')

    new_candidates = []
    for ep in all_eps:
        if not ep['uuid']:
            continue
        if ep['uuid'] in existing:
            continue
        # Skip episodes older than our latest known entry
        if ep['date'] and ep['date'] <= latest_date:
            continue
        if not is_likely_fan_episode(ep['title']):
            continue
        ep['is_must_go'] = bool(re.match(r'^conan must go:', ep['title'], re.IGNORECASE))
        new_candidates.append(ep)

    return new_candidates


def format_csv_row(ep):
    """
    Return a CSV-ready dict for a new episode candidate.
    Placeholders: name=???, location=???, occupation=???, topic=???
    """
    must_go = 'true' if ep.get('is_must_go') else 'false'
    return {
        'date':       ep['date'],
        'uuid':       ep['uuid'],
        'mustGo':     must_go,
        'title':      ep['title'],
        'name':       '???',
        'location':   '???',
        'occupation': '???',
        'topic':      '',
    }


def main():
    args = sys.argv[1:]
    verbose = '--json' not in args

    print('Conan Fan Map — RSS scraper')
    try:
        candidates = find_new_episodes(verbose=verbose)
    except Exception as e:
        print(f'  Error: {e}')
        sys.exit(1)

    if not candidates:
        print('  No new fan episodes found.')
        return

    if '--json' in args:
        print(json.dumps(candidates, indent=2, ensure_ascii=False))
        return

    print(f'\n  Found {len(candidates)} new candidate episode(s):\n')
    for ep in candidates:
        flag = ' [MUST GO]' if ep.get('is_must_go') else ''
        print(f"  {ep['date']}  {ep['title']}{flag}")
        print(f"           UUID: {ep['uuid']}")
        if ep.get('desc'):
            print(f"           Desc: {ep['desc'][:120]}…")
        print()

    if '--append' in args:
        fieldnames = ['date', 'uuid', 'mustGo', 'title', 'name', 'location', 'occupation', 'topic']
        rows_to_add = [format_csv_row(ep) for ep in candidates]
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            for row in rows_to_add:
                writer.writerow(row)
        print(f'  Appended {len(rows_to_add)} placeholder row(s) to episodes.csv')
        print('  Fill in the ??? fields (name, location, occupation) then run build.py')
    else:
        print('  Run with --append to add placeholder rows to episodes.csv')
        print('  Then fill in name / location / occupation for each new row.')


if __name__ == '__main__':
    main()
