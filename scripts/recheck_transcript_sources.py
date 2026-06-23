#!/usr/bin/env python3
"""
recheck_transcript_sources.py — Monthly completeness sweep for pending transcripts.

For every episode marked "pending" in data/transcripts/status_manifest.json, retry
the sources that don't need a real browser (HappyScribe, Podscripts.co, Musixmatch).
When a transcript is found, write it to data/transcripts/raw/, delete the placeholder
in data/transcripts/pending/, and flip the manifest entry to "available".

Podscribe is NOT checked here — its real episode-discovery path needs gstack's
headless browser (search must be scoped via showFilterId=1488), which isn't safely
automatable from an unattended cron context. Podscribe rechecks stay a manual/session
task; this script focuses on the three fully-scriptable vendors.

Usage:
  python3 scripts/recheck_transcript_sources.py            # check all pending
  python3 scripts/recheck_transcript_sources.py --limit 20 # check first 20 pending
  python3 scripts/recheck_transcript_sources.py --dry-run  # report only, no writes

Updates data/transcripts/status_manifest.json in place and logs every attempt to
data/transcripts/recheck_log.json.
"""

import csv
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import cloudscraper
except ImportError:
    print("Missing dependency. Run: pip3 install cloudscraper")
    sys.exit(1)

ROOT          = Path(__file__).parent.parent
DATA_DIR      = ROOT / 'data'
CSV_FILE      = DATA_DIR / 'episodes.csv'
RAW_DIR       = DATA_DIR / 'transcripts' / 'raw'
PENDING_DIR   = DATA_DIR / 'transcripts' / 'pending'
MANIFEST_FILE = DATA_DIR / 'transcripts' / 'status_manifest.json'
LOG_FILE      = DATA_DIR / 'transcripts' / 'recheck_log.json'

HAPPYSCRIBE_BASE = 'https://podcasts.happyscribe.com/conan-o-brien-needs-a-friend'
PODSCRIPTS_BASE  = 'https://podscripts.co/podcasts/conan-obrien-needs-a-friend'
MUSIXMATCH_SHOW  = 'conan-obrien-needs-a-friend-01gtgb2040cyw0vm46mcb9yyg7'

DRY_RUN = '--dry-run' in sys.argv
LIMIT   = None
for i, a in enumerate(sys.argv):
    if a == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])


def make_slug(title):
    s = title.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def load_episodes_by_title():
    with open(CSV_FILE, encoding='utf-8') as f:
        return {row['title']: row for row in csv.DictReader(f)}


def try_happyscribe(scraper, slug):
    url = f"{HAPPYSCRIBE_BASE}/{slug}"
    try:
        r = scraper.get(url, timeout=20)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        media = data.get('associatedMedia') or {}
        transcript = media.get('transcript') if isinstance(media, dict) else None
        if transcript:
            entries = re.findall(r'\[(\d{2}:\d{2}:\d{2})\.\d{2}\]\s*(.*?)(?=\[\d{2}:\d{2}:\d{2}\.\d{2}\]|$)', transcript, re.DOTALL)
            lines = [f"{ts}\n{html.unescape(text).strip()}" for ts, text in entries if text.strip()]
            body = '\n\n'.join(lines)
            if len(body) >= 200:
                return {'source': 'happyscribe', 'url': url, 'body': body}
    return None


def try_podscripts(slug, max_retries=4):
    url = f"{PODSCRIPTS_BASE}/{slug}"
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    attempt = 0
    while attempt < max_retries:
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                final_url = resp.geturl()
                body_html = resp.read(500_000).decode('utf-8', 'ignore')
                if final_url.rstrip('/') != url.rstrip('/') or 'Transcript and Discussion' not in body_html:
                    return None
                # Extract the transcript text block (best-effort, page-structure dependent)
                m = re.search(r'<div[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</div>\s*</div>', body_html, re.DOTALL | re.IGNORECASE)
                raw = m.group(1) if m else body_html
                text = re.sub(r'<[^>]+>', ' ', raw)
                text = html.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) >= 200:
                    return {'source': 'podscripts', 'url': url, 'body': text}
                return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                attempt += 1
                time.sleep(5 * attempt)
                continue
            return None
        except Exception:
            return None
    return None


def try_musixmatch(scraper, slug):
    url = f"https://podcasts.musixmatch.com/podcast/{MUSIXMATCH_SHOW}/episode/{slug}"
    try:
        r = scraper.get(url, timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    ssr = data.get('props', {}).get('pageProps', {}).get('ssr', {})
    ut = ssr.get('unsyncedTranscription')
    if not ut or not isinstance(ut, dict):
        return None
    lines = []
    for sec in ut.get('sections', []):
        if sec.get('isAds'):
            continue
        t = sec.get('referenceStartTime', 0)
        mins, secs = int(t) // 60, int(t) % 60
        lines.append(f"[{mins:02d}:{secs:02d}] {sec.get('speakerId','')}: {sec.get('transcript','')}")
    body = '\n'.join(lines)
    if len(body) >= 200:
        return {'source': 'musixmatch', 'url': url, 'body': body}
    return None


def write_transcript(ep_row, result):
    slug = make_slug(ep_row['title'])
    out_path = RAW_DIR / f"{ep_row['date']}_{slug}.md"
    frontmatter = (
        "---\n"
        f"episode_title: \"{ep_row['title']}\"\n"
        f"slug: {slug}\n"
        f"fan_name: \"{ep_row.get('name', '')}\"\n"
        f"fan_location: \"{ep_row.get('location', '')}\"\n"
        f"fan_occupation: \"{ep_row.get('occupation', '')}\"\n"
        f"source: {result['source']}\n"
        f"source_url: {result['url']}\n"
        f"date_published: \"{ep_row['date']}\"\n"
        "fetched_via: recheck_transcript_sources\n"
        "speaker_labels_present: false\n"
        f"found_on_recheck: \"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\"\n"
        "---\n\n"
        f"# Transcript: {ep_row['title']}\n\n"
        "---\n\n"
        f"{result['body']}\n"
    )
    out_path.write_text(frontmatter, encoding='utf-8')

    pending_path = PENDING_DIR / f"{ep_row['date']}_{slug}.md"
    if pending_path.exists():
        pending_path.unlink()

    return out_path


def main():
    episodes_by_title = load_episodes_by_title()
    manifest = json.loads(MANIFEST_FILE.read_text(encoding='utf-8'))

    pending_keys = [k for k, v in manifest.items() if v['status'] == 'pending']
    if LIMIT:
        pending_keys = pending_keys[:LIMIT]

    print(f"Rechecking {len(pending_keys)} pending episode(s) ({'DRY RUN' if DRY_RUN else 'LIVE'})\n")

    scraper = cloudscraper.create_scraper()
    log = []
    found_count = 0

    for i, key in enumerate(pending_keys):
        entry = manifest[key]
        title = entry['title']
        ep_row = episodes_by_title.get(title)
        if not ep_row:
            continue
        slug = make_slug(title)

        result = try_happyscribe(scraper, slug)
        if not result:
            result = try_podscripts(slug)
        if not result:
            result = try_musixmatch(scraper, slug)

        checked_sources = entry.get('checked_sources', {})
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        if result:
            found_count += 1
            checked_sources[result['source']] = 'found'
            print(f"[{i+1}/{len(pending_keys)}] ✓ FOUND: {title} (via {result['source']})")
            if not DRY_RUN:
                out_path = write_transcript(ep_row, result)
                entry['status'] = 'available'
                entry['transcript_file'] = str(out_path.relative_to(ROOT))
        else:
            for src in ('happyscribe', 'podscripts', 'musixmatch'):
                checked_sources.setdefault(src, 'not_found')
            print(f"[{i+1}/{len(pending_keys)}] · still pending: {title}")

        entry['checked_sources'] = checked_sources
        entry['last_checked'] = now
        log.append({'title': title, 'date': ep_row['date'], 'result': result['source'] if result else 'not_found', 'checked_at': now})

        if i < len(pending_keys) - 1:
            time.sleep(2.0)

    if not DRY_RUN:
        MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
        existing_log = []
        if LOG_FILE.exists():
            try:
                existing_log = json.loads(LOG_FILE.read_text())
            except json.JSONDecodeError:
                pass
        existing_log.extend(log)
        LOG_FILE.write_text(json.dumps(existing_log, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"\n{found_count} new transcript(s) found, {len(pending_keys) - found_count} still pending.")
    print("Note: Podscribe was not checked (needs gstack browse — run a manual session recheck for that vendor).")


if __name__ == '__main__':
    main()
