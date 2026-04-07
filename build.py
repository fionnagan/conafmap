#!/usr/bin/env python3
"""
build.py — Conan Fan Map build orchestrator

Usage:
  python build.py            # one-shot build → dist/index.html
  python build.py --watch    # rebuild on any src/ data/ template change
  python build.py --serve    # --watch + localhost:8000 with auto-refresh
"""

import csv
import json
import sys
import time
import threading
import os
from pathlib import Path

ROOT      = Path(__file__).parent
DATA_DIR  = ROOT / 'data'
SRC_DIR   = ROOT / 'src'
DIST_DIR  = ROOT / 'dist'
TEMPLATE  = ROOT / 'template.html'
OUT_FILE  = DIST_DIR / 'index.html'
TS_FILE   = DIST_DIR / '.build_ts'   # live-reload timestamp sentinel

# ── lib imports ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(ROOT))
from lib.geocode    import load_cache, save_cache, geo
from lib.countries  import country_from_location, display_location, occ_category
from lib.highlights import make_highlights, make_slug, MUST_GO_SEASONS, TEAMCOCO_BASE


# ── Build ─────────────────────────────────────────────────────────────────────

def build(verbose=False):
    t0 = time.time()
    DIST_DIR.mkdir(exist_ok=True)

    # 1. Load supporting data
    rich_data = json.loads((DATA_DIR / 'rich_data.json').read_text(encoding='utf-8'))
    cache     = load_cache()
    cache_dirty = False

    # 2. Parse episodes.csv → fan dicts
    fans = []
    used_slugs = set()
    with open(DATA_DIR / 'episodes.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            date       = row['date'].strip()
            uuid       = row['uuid'].strip()
            must_go    = row['mustGo'].strip().lower() in ('true', '1', 'yes')
            title      = row['title'].strip()
            name       = row['name'].strip()
            location   = row['location'].strip()
            occupation = row['occupation'].strip()
            topic      = row.get('topic', '').strip()

            # Geocode
            orig_len = len(cache)
            coords   = geo(location, cache, verbose=verbose)
            if len(cache) != orig_len:
                cache_dirty = True

            country       = country_from_location(location)
            disp_loc      = display_location(location, country)
            cat           = occ_category(occupation)
            highlights, fan_q, conan_r = make_highlights(name, location, occupation, topic, title, rich_data)
            must_go_season = MUST_GO_SEASONS.get(title, 0) if must_go else 0
            episode_slug   = make_slug(title)
            teamcoco_url   = (TEAMCOCO_BASE + episode_slug) if (uuid or title) else ''
            slug           = episode_slug
            if slug in used_slugs:
                slug = make_slug(title + ' ' + name)
            used_slugs.add(slug)

            fans.append({
                'date':             date,
                'name':             name,
                'fullName':         name,
                'location':         location,
                'displayLocation':  disp_loc,
                'country':          country,
                'coords':           coords,
                'occupation':       occupation,
                'occupationCategory': cat,
                'episode':          title,
                'simplecastId':     uuid,
                'mustGo':           must_go,
                'mustGoSeason':     must_go_season,
                'slug':             slug,
                'teamcocoUrl':      teamcoco_url,
                'highlights':       highlights,
                'fanQuestion':      fan_q,
                'conanResponse':    conan_r,
                'topic':            topic,
            })

    # Persist any new geocache entries
    if cache_dirty:
        save_cache(cache)
        if verbose:
            print(f'  geocache updated ({len(cache)} entries)')

    # 3. Serialise FANS to JS
    fans_js = _fans_to_js(fans)

    # 4. Read src/ files
    styles  = (SRC_DIR / 'styles.css').read_text(encoding='utf-8')
    scripts = '\n\n'.join(
        (SRC_DIR / f).read_text(encoding='utf-8')
        for f in ('map.js', 'charts.js', 'table.js', 'spotlight.js', 'topnav.js')
    )

    # 5. Render template
    html = TEMPLATE.read_text(encoding='utf-8')
    html = html.replace('{{STYLES}}',    styles)
    html = html.replace('{{FANS_JSON}}', fans_js)
    html = html.replace('{{SCRIPTS}}',  scripts)

    # 6. Write output
    OUT_FILE.write_text(html, encoding='utf-8')
    TS_FILE.write_text(str(time.time()))   # triggers live-reload

    elapsed = time.time() - t0
    must_go_count = sum(1 for f in fans if f['mustGo'])
    countries     = len({f['country'] for f in fans if f['country'] != 'Unknown'})
    print(f'  ✓ Built {len(fans)} fans · {countries} countries · {must_go_count} Must Go '
          f'→ dist/index.html  ({elapsed:.2f}s)')
    return fans


def _j(val):
    """json.dumps with ensure_ascii=False so flag emojis stay as Unicode."""
    return json.dumps(val, ensure_ascii=False)


def _fans_to_js(fans):
    lines = ['const FANS = [']
    for f in fans:
        must_go_js = 'true' if f['mustGo'] else 'false'
        lines.append(
            f"  {{"
            f"date:{_j(f['date'])}, name:{_j(f['name'])}, "
            f"fullName:{_j(f['fullName'])}, "
            f"location:{_j(f['location'])}, "
            f"displayLocation:{_j(f['displayLocation'])}, "
            f"country:{_j(f['country'])}, "
            f"coords:{_j(f['coords'])},\n"
            f"    occupation:{_j(f['occupation'])}, "
            f"occupationCategory:{_j(f['occupationCategory'])},\n"
            f"    episode:{_j(f['episode'])}, "
            f"simplecastId:{_j(f['simplecastId'])},\n"
            f"    highlights:{_j(f['highlights'])},\n"
            f"    fanQuestion:{_j(f['fanQuestion'])}, "
            f"conanResponse:{_j(f['conanResponse'])}, "
            f"topic:{_j(f['topic'])},\n"
            f"    mustGo:{must_go_js}, mustGoSeason:{f['mustGoSeason']}, "
            f"slug:{_j(f['slug'])},\n"
            f"    teamcocoUrl:{_j(f['teamcocoUrl'])} }},"
        )
    lines.append('];')
    return '\n'.join(lines)


# ── Watch ─────────────────────────────────────────────────────────────────────

def _mtimes():
    paths = [TEMPLATE] + list(SRC_DIR.iterdir()) + list(DATA_DIR.iterdir())
    return {str(p): p.stat().st_mtime for p in paths if p.is_file()}

def watch(serve=False):
    if serve:
        _start_server()
    print('  Watching src/, data/, template.html for changes…  (Ctrl+C to stop)')
    last = _mtimes()
    while True:
        time.sleep(0.8)
        current = _mtimes()
        changed = [p for p in current if current[p] != last.get(p)]
        if changed:
            rel = [Path(p).name for p in changed]
            print(f'\n  Changed: {", ".join(rel)}')
            try:
                build(verbose=False)
            except Exception as e:
                print(f'  ✗ Build error: {e}')
            last = _mtimes()


# ── Dev server ────────────────────────────────────────────────────────────────

LIVE_RELOAD_SNIPPET = """
<script>
(function(){
  var ts=null;
  setInterval(function(){
    fetch('/.build_ts?_='+Date.now()).then(r=>r.text()).then(function(t){
      if(ts===null){ts=t;return;}
      if(t!==ts){ts=t;location.reload();}
    }).catch(function(){});
  },800);
})();
</script>
"""

def _start_server(port=8000):
    import http.server
    import socketserver

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DIST_DIR), **kw)

        def do_GET(self):
            # Inject live-reload snippet into the main HTML file
            if self.path.split('?')[0] in ('/', '/index.html'):
                content = OUT_FILE.read_bytes()
                injected = content.replace(b'</body>', LIVE_RELOAD_SNIPPET.encode() + b'</body>', 1)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(injected)))
                self.end_headers()
                self.wfile.write(injected)
            else:
                super().do_GET()

        def log_message(self, fmt, *args):
            pass   # suppress per-request logs

    def _serve():
        with socketserver.TCPServer(('', port), Handler) as httpd:
            httpd.allow_reuse_address = True
            print(f'  Serving → http://localhost:{port}/')
            httpd.serve_forever()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]
    print('Conan Fan Map — build')
    if '--serve' in args:
        build(verbose=True)
        watch(serve=True)
    elif '--watch' in args:
        build(verbose=True)
        watch(serve=False)
    else:
        build(verbose=True)
