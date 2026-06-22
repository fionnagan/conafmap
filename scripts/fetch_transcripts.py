#!/usr/bin/env python3
"""
fetch_transcripts.py — Pull HappyScribe transcripts for fan episodes, no browser needed.

HappyScribe blocks plain urllib/curl with a Cloudflare JS challenge, but `cloudscraper`
(a Python library purpose-built to solve Cloudflare's challenge without a real browser)
gets through cleanly. The transcript itself lives in a clean JSON-LD <script> block on
the page (schema.org PodcastEpisode-ish Article), so parsing is `json.loads()`, not
HTML scraping.

Usage:
  python3 scripts/fetch_transcripts.py                  # fetch all episodes in episodes.csv
  python3 scripts/fetch_transcripts.py --limit 10        # fetch first 10 missing
  python3 scripts/fetch_transcripts.py --title "Hot Athens"   # fetch one by title
  python3 scripts/fetch_transcripts.py --force           # re-fetch even if file exists
  python3 scripts/fetch_transcripts.py --dry-run         # show what would be fetched

Output: data/transcripts/raw/{date}_{slug}.md  (frontmatter + timestamped transcript)
Failures logged to: data/transcripts/fetch_log.json
"""

import csv
import html
import json
import re
import sys
import time
from pathlib import Path

try:
    import cloudscraper
except ImportError:
    print("Missing dependency. Run: pip3 install cloudscraper")
    sys.exit(1)

ROOT        = Path(__file__).parent.parent
DATA_DIR    = ROOT / 'data'
CSV_FILE    = DATA_DIR / 'episodes.csv'
RAW_DIR     = DATA_DIR / 'transcripts' / 'raw'
LOG_FILE    = DATA_DIR / 'transcripts' / 'fetch_log.json'
SHOW_SLUG   = 'conan-o-brien-needs-a-friend'
BASE_URL    = f'https://podcasts.happyscribe.com/{SHOW_SLUG}'

SLEEP_BETWEEN_REQUESTS = 2.0   # seconds — be polite, this is someone else's server

# ── CLI args ──────────────────────────────────────────────────────────────────
DRY_RUN      = '--dry-run' in sys.argv
FORCE        = '--force'   in sys.argv
LIMIT        = None
TITLE_FILTER = None
for i, a in enumerate(sys.argv):
    if a == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])
    if a == '--title' and i + 1 < len(sys.argv):
        TITLE_FILTER = sys.argv[i + 1].strip()


def make_slug(title):
    """Matches HappyScribe's own slugification: lowercase, any run of
    non-alphanumeric chars (including apostrophes) collapses to one hyphen."""
    s = title.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def load_episodes():
    if not CSV_FILE.exists():
        print(f"Missing {CSV_FILE}")
        sys.exit(1)
    with open(CSV_FILE, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def parse_transcript_jsonld(html_text):
    """
    Extract (headline, date_published, abstract, transcript_raw, word_count)
    from the page's schema.org JSON-LD block. Returns None if not found.
    """
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_text, re.DOTALL):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        media = data.get('associatedMedia') or {}
        transcript = media.get('transcript') if isinstance(media, dict) else None
        if transcript:
            return {
                'headline':       data.get('headline', ''),
                'date_published': data.get('datePublished', ''),
                'abstract':       data.get('abstract', ''),
                'transcript_raw': transcript,
                'word_count':     data.get('wordCount', ''),
            }
    return None


def parse_episode_description(html_text):
    """
    The JSON-LD 'abstract' field is generic SEO boilerplate, not the real
    per-episode description. The actual description lives in a plain div.
    Falls back to '' if not found.
    """
    m = re.search(
        r'<div class="episode-description-text">\s*<p>(.*?)</p>',
        html_text, re.DOTALL
    )
    if not m:
        return ''
    raw = m.group(1)
    raw = re.sub(r'<br\s*/?>', ' ', raw)          # collapse <br> to space
    raw = re.sub(r'<[^>]+>', '', raw)              # strip any remaining tags
    raw = html.unescape(raw).strip()
    # Strip the boilerplate CTA/sponsor text every episode shares — keep only
    # the unique per-episode summary sentence(s) before it.
    raw = re.split(r'Wanna get a chance to talk to Conan', raw)[0].strip()
    return raw


def format_transcript_body(transcript_raw):
    """
    Convert '[00:00:03.03]  text  [00:00:13.04]  text' into our standard
    'HH:MM:SS\ntext\n\n' block format, matching the manually-captured files.
    """
    html.unescape  # noqa — used below
    entries = re.findall(r'\[(\d{2}:\d{2}:\d{2})\.\d{2}\]\s*(.*?)(?=\[\d{2}:\d{2}:\d{2}\.\d{2}\]|$)', transcript_raw, re.DOTALL)
    lines = []
    for ts, text in entries:
        text = html.unescape(text).strip()
        if text:
            lines.append(f"{ts}\n{text}")
    return '\n\n'.join(lines)


def fetch_one(scraper, ep, raw_dir):
    title = ep['title']
    slug  = make_slug(title)
    url   = f"{BASE_URL}/{slug}"
    out_path = raw_dir / f"{ep['date']}_{slug}.md"

    if out_path.exists() and not FORCE:
        return {'title': title, 'status': 'skipped_exists'}

    if DRY_RUN:
        return {'title': title, 'status': 'dry_run', 'url': url, 'would_write': str(out_path)}

    try:
        r = scraper.get(url, timeout=20)
    except Exception as e:
        return {'title': title, 'status': 'failed', 'reason': f'request_error: {e}', 'url': url}

    if r.status_code != 200:
        return {'title': title, 'status': 'failed', 'reason': f'http_{r.status_code}', 'url': url}

    parsed = parse_transcript_jsonld(r.text)
    if not parsed:
        return {'title': title, 'status': 'failed', 'reason': 'no_jsonld_transcript', 'url': url}

    real_description = parse_episode_description(r.text) or parsed['abstract']
    body = format_transcript_body(parsed['transcript_raw'])
    if len(body) < 200:
        return {'title': title, 'status': 'failed', 'reason': 'transcript_too_short', 'url': url}

    frontmatter = (
        "---\n"
        f"episode_title: \"{title}\"\n"
        f"slug: {slug}\n"
        f"fan_name: \"{ep.get('name', '')}\"\n"
        f"fan_location: \"{ep.get('location', '')}\"\n"
        f"fan_occupation: \"{ep.get('occupation', '')}\"\n"
        f"source: happyscribe\n"
        f"source_url: {url}\n"
        f"date_published: \"{parsed['date_published']}\"\n"
        f"word_count: {parsed['word_count'] or 'null'}\n"
        f"fetched_via: cloudscraper\n"
        f"speaker_labels_present: false\n"
        "---\n\n"
        f"# Transcript: {title}\n\n"
        f"**Episode description:** {real_description}\n\n"
        "---\n\n"
        f"{body}\n"
    )

    out_path.write_text(frontmatter, encoding='utf-8')
    return {'title': title, 'status': 'success', 'url': url, 'chars': len(body)}


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    episodes = load_episodes()

    if TITLE_FILTER:
        episodes = [e for e in episodes if e['title'].strip().lower() == TITLE_FILTER.lower()]
        if not episodes:
            print(f"No episode found matching title: {TITLE_FILTER}")
            sys.exit(1)

    if not FORCE:
        pending = []
        for ep in episodes:
            slug = make_slug(ep['title'])
            out_path = RAW_DIR / f"{ep['date']}_{slug}.md"
            if not out_path.exists():
                pending.append(ep)
        episodes = pending

    if LIMIT:
        episodes = episodes[:LIMIT]

    print(f"Conan Fan Map — transcript fetcher ({'DRY RUN' if DRY_RUN else 'LIVE'})")
    print(f"  {len(episodes)} episode(s) to process\n")

    scraper = cloudscraper.create_scraper()
    results = []
    for i, ep in enumerate(episodes):
        result = fetch_one(scraper, ep, RAW_DIR)
        results.append(result)
        status = result['status']
        marker = {'success': '✓', 'skipped_exists': '·', 'dry_run': '?', 'failed': '✗'}.get(status, '?')
        print(f"  [{i+1}/{len(episodes)}] {marker} {ep['title']}  ({status}{': ' + result.get('reason', '') if status == 'failed' else ''})")
        if status == 'success' and i < len(episodes) - 1:
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    if not DRY_RUN:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing_log = []
        if LOG_FILE.exists():
            try:
                existing_log = json.loads(LOG_FILE.read_text())
            except json.JSONDecodeError:
                pass
        existing_log.extend(results)
        LOG_FILE.write_text(json.dumps(existing_log, indent=2, ensure_ascii=False))

    succeeded = sum(1 for r in results if r['status'] == 'success')
    failed    = [r for r in results if r['status'] == 'failed']
    print(f"\n  {succeeded} succeeded, {len(failed)} failed, {len(results) - succeeded - len(failed)} skipped")
    if failed:
        print("\n  Failures:")
        for r in failed:
            print(f"    - {r['title']}: {r['reason']}")


if __name__ == '__main__':
    main()
