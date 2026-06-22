#!/usr/bin/env python3
"""
fetch_teamcoco_canonical.py — TeamCoco is the Bible for episode title, air date,
and description. This script pulls the official episode list directly from
teamcoco.com and writes a clean, re-fetchable canonical file.

Why TeamCoco: it's the official show page, not a third-party transcript vendor.
Other sources (HappyScribe, Podscripts.co, Podscribe, Musixmatch) sometimes carry
typos, truncated titles, or wrong apostrophes — TeamCoco's listing is ground truth
for what an episode is actually called and when it aired. Cross-referencing against
this file is what caught real errors this session (e.g. "Energeeza" mis-dated by a
week, "The Emotional Health of My Dog" actually being "...My Don Johnson").

Source: https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes
        (Next.js page; episode list lives in __NEXT_DATA__ -> pageProps.pageData
        .blocks[name="show-episodes"].props.episodes)

Output: data/teamcoco_canonical.json
  {
    "<guid>": {
      "title": str,
      "date": "YYYY-MM-DD",
      "description": str (HTML stripped, ad/CTA boilerplate trimmed),
      "description_html": str (raw, untrimmed),
      "url": str (teamcoco.com episode page path),
      "audio_url": str (decoded from the signed playbackUrl JWT)
    },
    ...
  }

Usage:
  python3 scripts/fetch_teamcoco_canonical.py
"""

import base64
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT       = Path(__file__).parent.parent
DATA_DIR   = ROOT / 'data'
OUT_FILE   = DATA_DIR / 'teamcoco_canonical.json'
URL        = 'https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes'

AD_BOILERPLATE_MARKERS = [
    r'Wanna get a chance to talk to Conan.*',
    r'Get access to all the podcasts you love.*',
    r'Hosted by Simplecast.*',
]


def fetch_html():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', 'ignore')


def decode_playback_url(playback_url):
    """playbackUrl is '/api/playback/<jwt>'; the JWT payload's 'url' field is the real MP3."""
    if not playback_url or '.' not in playback_url:
        return None
    jwt = playback_url.rsplit('/', 1)[-1]
    parts = jwt.split('.')
    if len(parts) != 3:
        return None
    payload = parts[1]
    payload += '=' * (-len(payload) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data.get('url')
    except Exception:
        return None


def clean_description(raw_html):
    text = re.sub(r'<[^>]+>', ' ', raw_html or '')
    text = re.sub(r'&nbsp;| ', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    for pattern in AD_BOILERPLATE_MARKERS:
        text = re.split(pattern, text)[0].strip()
    return text


def parse_pub_date(s):
    """'Thursday, June 18, 2026' -> '2026-06-18'"""
    try:
        return datetime.strptime(s, '%A, %B %d, %Y').strftime('%Y-%m-%d')
    except ValueError:
        return None


def main():
    print(f"Fetching {URL} ...")
    html_text = fetch_html()

    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_text)
    if not m:
        print("Could not find __NEXT_DATA__ on the page — TeamCoco may have changed their page structure.")
        sys.exit(1)

    data = json.loads(m.group(1))
    blocks = data['props']['pageProps']['pageData']['blocks']
    ep_block = next((b for b in blocks if b.get('name') == 'show-episodes'), None)
    if not ep_block:
        print("Could not find the show-episodes block — page structure changed.")
        sys.exit(1)

    raw_episodes = ep_block['props']['episodes']
    print(f"Found {len(raw_episodes)} episodes on the page.")

    canonical = {}
    skipped = 0
    for ep in raw_episodes:
        guid = (ep.get('guid') or {}).get('#text')
        date = parse_pub_date(ep.get('pubDate', ''))
        if not guid or not date:
            skipped += 1
            continue
        canonical[guid] = {
            'title': ep['title'],
            'date': date,
            'description': clean_description(ep.get('description', '')),
            'description_html': ep.get('description_html', ''),
            'url': ep.get('url', ''),
            'audio_url': decode_playback_url(ep.get('playbackUrl', '')),
        }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(canonical, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Wrote {len(canonical)} canonical episodes to {OUT_FILE} ({skipped} skipped, missing guid/date).")


if __name__ == '__main__':
    main()
