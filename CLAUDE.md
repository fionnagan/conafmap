# Conan Fan Map — Claude Code Project Context

> This file is the single source of truth for picking up this project in Claude Code.
> Read it fully before touching any file. Companion docs live in `docs/`.

---

## gstack

Use the `/browse` skill from gstack for all web browsing tasks. Never use `mcp__claude-in-chrome__*`
tools.

Available gstack skills: `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`,
`/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`,
`/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`,
`/setup-browser-cookies`, `/setup-deploy`, `/setup-gbrain`, `/retro`, `/investigate`,
`/document-release`, `/document-generate`, `/codex`, `/cso`, `/autoplan`, `/plan-devex-review`,
`/devex-review`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`.

---

## What This Project Is

An interactive world map of every fan who has appeared on the **"Conan O'Brien Needs a Fan"**
podcast segment and the HBO travel show **"Conan Must Go"** (~196 fans, 2021–2026), plus
**"Ask the Map"** — a live, citation-backed RAG Q&A over the full fan-episode transcript corpus.

**Live site:** https://conafmap.vercel.app (Vercel; serves committed `dist/`, see [[deploy-model]]).
**Build script:** `build.py` (reads `data/`, renders `dist/index.html` via `template.html` + `src/`).

See `docs/STAKEHOLDERS.md` for the full audience brief.

---

## Current File State

The project **has been refactored** into a proper data/src/build structure, and the RAG
Q&A layer shipped on top of it.

```
build.py                    # Build script: data/ + template.html + src/ -> dist/index.html
template.html               # Jinja-ish HTML skeleton
src/                        # map.js, charts.js, table.js, ask.js, spotlight.js, topnav.js, styles.css
data/
├── episodes.csv            # source of truth — one row per fan (two-fan episodes split into 2 rows)
├── rich_data.json          # highlights + fan questions
├── geocache.json           # cached coordinates
├── teamcoco_canonical.json # canonical episode title/date/description ("the Bible")
├── transcripts/
│   ├── raw/                # 195 captured transcripts (.md, per-source formats)
│   ├── normalized/         # 195 transcripts normalized to one [HH:MM:SS]/Speaker grammar
│   └── status_manifest.json
└── rag/                    # committed RAG artifacts (bundled into the serverless fn)
    ├── chunks.jsonl, chunks_contextual.jsonl   # build intermediates
    ├── embeddings.npz       # int8 Voyage voyage-3 matrices (contextual + metadata)
    ├── chunks_meta.json     # per-chunk metadata + corpus_hash
    ├── bm25.json            # contextual BM25 index
    └── host_profiles.json   # cross-episode Conan/Sona/Matt profiles
api/
├── ask.py                  # /api/ask serverless endpoint (facts + RAG, cache, rate limit, Notion log)
├── retrieval.py            # hybrid retrieval (vector + BM25 RRF) + host profiles + citations
├── fans_context.json       # facts table emitted by build.py
└── requirements.txt        # anthropic, numpy
scripts/                    # data pipeline (see "Ask the Map" section below)
dist/index.html             # built output (committed; Vercel serves it)
```

---

## Ask the Map — RAG Q&A (LIVE)

`/api/ask` answers natural-language questions grounded in transcript evidence with clickable
episode+timestamp citations, falling back to a facts-only answer (from `fans_context.json`)
when retrieval is unavailable. Detailed notes live in the [[fan-qa-endpoint]] memory.

**Offline build pipeline (`scripts/`), in order:**
1. `fetch_transcripts.py` / `recheck_transcript_sources.py` — gather transcripts → `data/transcripts/raw/`
2. `normalize_transcripts.py` — 5 source formats → one canonical `[HH:MM:SS]` (+ optional `Speaker N:`) grammar → `normalized/`
3. `chunk_transcripts.py` — speaker-turn-aware chunks (never split mid-turn) → `data/rag/chunks.jsonl`
4. `contextualize_chunks.py` — per-chunk LLM context blurb (transcript prompt-cached) + free metadata baseline → `chunks_contextual.jsonl`
5. `embed_chunks.py` — Voyage `voyage-3`, int8 unit-vector matrices → `embeddings.npz` + `chunks_meta.json`
6. `build_bm25.py` — contextual BM25 inverted index → `bm25.json`
7. `build_host_profiles.py` — map-reduce per recurring host → `host_profiles.json`
8. `run_eval.py` — vector-only vs hybrid eval; `verify_timestamps.py` — citation-integrity check
9. `test_chunk_transcripts.py` — chunker unit tests

**Request flow (`api/ask.py` → `api/retrieval.py`):** response-cache GET (key includes
`_CACHE_GEN` + `corpus_hash`) → Voyage query embed (fail-open) → vector top-50 + BM25 top-50
→ RRF → top-15 chunks → inject host profile if the question names Conan/Sona/Matt → Haiku
(facts in cached system block, chunks/host in uncached user message) → citation validation →
cache SET → return `{answer, citations}`.

**Gotchas (learned the hard way):**
- **Env var names are non-canonical.** Voyage key = `VoyageAPI` (not `VOYAGE_API_KEY`); Anthropic
  = `CLAUDE` / `Anthropic_API`. `retrieval._voyage_key()` does multi-name fallback. Set keys for
  BOTH Preview and Production scopes in Vercel.
- **Vercel builds each `api/*.py` as an isolated function.** Sibling imports (`import retrieval`)
  fail at runtime unless the module is in `vercel.json` `includeFiles` AND
  `sys.path.insert(0, dirname(__file__))` is present. All `data/rag/*` artifacts must be in
  `includeFiles` too. Failures here are SILENT (fail-open to facts) — add a temp `_diag` field
  to debug, never guess.
- **`_CACHE_GEN`** (in `api/ask.py`, currently `r4`) is bumped whenever answer *behavior* changes
  (not just data) to flush stale cached answers. `MAX_TOKENS` is 400.
- **Two-fan episodes** ("Don't Sit Down on Wet Grass" → Katelyn + Farhan; "A.T.O.S" → Megan +
  Christian) are split across raw/normalized/`episodes.csv` (suffixed UUIDs). Split the raw files,
  not just normalized, or `normalize_transcripts.py` regenerates the unsplit version.
- **Local `build.py --serve` is static-only** — `/api/ask` only runs on a real Vercel deploy;
  validate on production (preview deploys are auth-walled).

---

## Current Feature Set (fully working)

- **Leaflet.js map** — CartoDB dark tiles, MarkerCluster, scroll-wheel zoom
- **Two pin colors** — TeamCoco orange `#F26522` (fan), HBO blue `#0057B8` (Must Go)
- **Popups** — 640px wide, scrollable, contain: badge, name, episode, location,
  occupation, fan's question, highlights, Simplecast audio player, TeamCoco link
- **Stats bar** — Fans Featured, Countries, Must Go Guests, % World Nations
- **Analytics charts** (Chart.js) — Top Countries (bar), Continents (pie),
  Occupation Categories (donut), Episodes Over Time (line)
- **Filter bar** — Search, Country, Occupation Category, Appearances (Podcast / Must Go HBO / All)
- **Episode table** — Date, Fan, Location (city + flag emoji), Occupation,
  Episode title (linked to teamcoco.com), Fan's Question, Appearances badge
- **Header** — Podcast logo, inline SVG buttons for Apple Podcasts, Spotify,
  Amazon Music, SiriusXM (no external image dependencies)
- **Must Go season badges** — "Must Go — Season 1" / "Must Go — Season 2"

---

## Design Tokens (CSS Variables)

```css
--orange:       #F26522    /* TeamCoco orange — fan pins, accents, headings */
--orange-dark:  #c94e12
--orange-glow:  rgba(242,101,34,0.25)
--mustgo:       #0057B8    /* HBO blue — Must Go pins, badges, legend dot */
--mustgo-glow:  rgba(0,87,184,0.20)
--bg:           #111318    /* page background */
--bg2:          #181c24    /* card / section background */
--bg3:          #1e2436    /* elevated surface */
--border:       #2a3040
--text:         #e8eaf0
--text-muted:   #7a8299
--blue:         #3498db
```

---

## FANS Data Object Shape (JavaScript)

Every entry in the `FANS` array has these fields:

```javascript
{
  date:              "2024-10-31",           // ISO date
  name:              "Penny",
  fullName:          "Penny",
  location:          "Christchurch",         // raw location string (used for geocoding)
  displayLocation:   "Christchurch — New Zealand",  // formatted (stripped of country by flagLoc())
  country:           "New Zealand",          // used for continent chart + flag lookup
  coords:            [-43.53, 172.64],       // [lat, lng]
  occupation:        "Recently Engaged Person",
  occupationCategory:"Other",
  episode:           "It's An Honor Just To Be Engaged",
  simplecastId:      "3a164557-...",         // "" if no audio player available
  mustGo:            true,
  mustGoSeason:      2,                      // 0 = not Must Go, 1 or 2 = season
  teamcocoUrl:       "https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes/its-an-honor-just-to-be-engaged",
  highlights:        ["...", "...", "..."],  // [] for generic episodes
  fanQuestion:       "...",                  // "" if unknown
  topic:             "...",                  // about_topic from source data
}
```

---

## generate_map.py — Key Structures

```
DISPLAY_LOC       dict   location string → "City, ST — Country" formatted string
GEO               dict   location string → [lat, lng]
RICH              dict   episode title  → { highlights:[], fanQuestion:"" }
MUST_GO_SEASONS   dict   episode title  → season number (1 or 2)
EPISODES          list   tuples: (date, uuid, mustGo, title, name, location, occupation)
                          OR    (date, uuid, mustGo, title, name, location, occupation, about_topic)

country_from_location(loc) → country name string
display_location(loc, country) → formatted display string
make_highlights(name, loc, occ, topic, title) → ([highlights], fanQuestion)
build_fans() → list of fan dicts
js_fans(fans) → JavaScript "const FANS = [...];" string
```

**CRITICAL:** The Canada check in `country_from_location()` must come **before** the
US state-code checks. The string `", ca"` appears inside `"ontario, canada"` and would
falsely match California if checked first. This bug was fixed — don't regress it.

---

## JavaScript Helpers in the HTML

```javascript
makeIcon(mustGo)           // returns Leaflet divIcon — orange or HBO blue
buildPopup(f)              // builds popup HTML for a fan object
flagLoc(f)                 // strips " — Country" from displayLocation, appends flag emoji
COUNTRY_FLAGS              // dict: country name → flag emoji (34 countries)
applyFilters()             // reads all filter inputs, updates `filtered` array
sortTable(key)             // sorts by field, toggles asc/desc
renderTable()              // renders filtered+sorted FANS to #epTableBody
populateFilters()          // fills country + category <select> dropdowns
```

---

## Map Configuration

```javascript
L.map('map', {
  worldCopyJump:      false,
  scrollWheelZoom:    true,       // enabled — Google Maps style
  maxBounds:          [[-90,-180],[90,180]],
  maxBoundsViscosity: 1.0,
  minZoom:            2,
}).setView([20, 10], 2);

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  noWrap: true,   // prevents world duplication — critical for correct marker placement
}).addTo(map);
```

---

## Episode Table — Column Order

| Date | Fan | Location | Occupation | Episode | Fan's Question | Appearances |

- Location uses `flagLoc(f)` → e.g. "Toronto, ON 🇨🇦", "Miami, FL 🇺🇸", "Bergen 🇳🇴"
- Episode title is a link to `f.teamcocoUrl` when available
- Appearances badge: "Must Go S1" or "Must Go S2" (HBO blue), blank for podcast-only fans

---

## Stats Bar — Current Cards

1. **Fans Featured** (183)
2. **Countries** (34)
3. **Must Go Guests** (13)
4. **% World Nations** (~17%)

The "Fan Episodes" card was removed as redundant with "Fans Featured."

---

## Charts — Order and Type

1. **Top Countries Represented** — horizontal bar chart
2. **Continents Represented** — pie chart
3. **Occupation Categories** — donut chart
4. **Fan Episodes Over Time** — line chart (2021–2026)

---

## Platform Links (Header)

All logos are embedded as **inline base64 SVG data URIs** — no external image dependencies.

| Platform     | Button color    | URL                                                              |
|--------------|-----------------|------------------------------------------------------------------|
| Apple Podcasts | Purple gradient | itunes.apple.com/us/podcast/.../id1438054347                  |
| Spotify      | #1db954 green   | open.spotify.com/show/3u26tlz7A3WyWRtXliX9a9                    |
| Amazon Music | #0f1111 dark    | music.amazon.com/podcasts/848cefd0-...                           |
| SiriusXM     | #0000cc blue    | sxm.app.link/CONAFWEB                                            |

---

## Known Gotchas

1. **Date parsing** — always use `new Date(f.date + 'T12:00:00')` not `new Date(f.date)`.
   The bare ISO string parses as UTC midnight, which shifts the display date by one day
   in US timezones. This is already fixed; don't revert it.

2. **World-wrap** — `noWrap: true` on the tile layer is required. Without it, markers
   placed near the antimeridian (e.g. New Zealand) render on ghost copies of the map and
   the pin click behavior breaks.

3. **Popup cut-off** — `.popup-inner` has `max-height: 70vh; overflow-y: auto` so tall
   popups scroll rather than getting clipped by the map container edge.

4. **Generic highlights** — `make_highlights()` returns `[]` when no real data exists.
   The popup only renders the highlights section when `f.highlights.length > 0`.
   Don't reintroduce the old three-line filler template.

5. **Flag regex** — `flagLoc()` strips trailing ` — <text>` using a Unicode em-dash
   (`\u2014`), not a regular hyphen. The DISPLAY_LOC dict uses em-dashes consistently.

6. **Must Go fans without Simplecast IDs** — several Must Go episode entries have
   `simplecastId: ""`. The popup only renders the `<iframe>` when the ID is non-empty.

7. **teamcocoUrl slugs** — generated by `make_slug()` which lowercases, strips
   non-alphanumeric (except hyphens), and collapses spaces to hyphens. Works for most
   titles but verify manually for titles with apostrophes (e.g. "It's An Honor...").

---

## Current Fan Count Breakdown

| Category          | Count |
|-------------------|-------|
| Total fans        | 183   |
| Must Go Season 1  | 8     |
| Must Go Season 2  | 5     |
| Podcast only      | 170   |
| Countries         | 34    |
| Years covered     | 2021–2026 |

---

## Wanted Next Features (prioritized)

1. **Shareable pin URLs** — `?fan=episode-slug` opens that pin's popup on load; URL
   updates in browser bar when any popup opens (good for fans sharing their pin)
2. **Find a fan near me** — geolocation button flies to nearest pin and opens popup
3. **Embed mode** — `?embed=1` hides header/footer/table for iframe use on teamcoco.com
4. **Export analytics PNG** — one-click screenshot of charts section (for distributors)
5. **Mobile bottom sheet** — replace Leaflet popup with a slide-up sheet on small screens
6. **Choropleth layer toggle** — shade countries by fan count (Team Coco / HBO use case)
7. **Expandable question column** — click to expand full text inline in table

---

## How to Add a New Fan Episode

See `docs/DATA_GUIDE.md` for the full guide. Quick version (map only):

1. Add a row to `data/episodes.csv` (`date,uuid,mustGo,title,name,location,occupation,topic`).
   For a two-fan episode, add two rows with the same base UUID suffixed `-fanname`.
2. If the location is new, `build.py` geocodes it via Nominatim and caches to `geocache.json`.
3. Optionally add highlights + fan question to `data/rich_data.json`.
4. Run `python3 build.py` — output is `dist/index.html` (commit it; Vercel serves committed `dist/`).

**To make a new episode answerable by Ask the Map (RAG):** also fetch its transcript into
`data/transcripts/raw/`, then re-run the `scripts/` pipeline (normalize → chunk → contextualize
→ embed → bm25; rebuild host profiles only if needed). Bump `_CACHE_GEN` in `api/ask.py` only if
answer *behavior* changes — `corpus_hash` already invalidates the response cache when the data
changes.

---

## Architecture (refactor complete)

The single-HTML `generate_map.py` era is over — the project is now `data/` (source of truth) +
`src/` (JS/CSS) + `template.html` + `build.py` → committed `dist/index.html`, with the `api/` +
`scripts/` + `data/rag/` RAG layer on top (see "Ask the Map" above and the [[fan-qa-endpoint]] /
[[deploy-model]] memories).
