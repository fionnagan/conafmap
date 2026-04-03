# Claude Code — Refactor Prompt

Copy and paste the block below as your **first message** in a new Claude Code session.
Make sure `conan-fan-map.html` and `generate_map.py` are in the working directory.

---

```
I'm handing you a project to restructure and elevate. Read these two files
before doing anything else:

  - conan-fan-map.html   (built output — ~1,700-line single-file app)
  - generate_map.py      (Python build script — ~850 lines, all data inside)

Also read CLAUDE.md for full project context before proceeding.

─── WHAT THIS IS ────────────────────────────────────────────────────────────

An interactive world map of every fan who has appeared on the
"Conan O'Brien Needs a Fan" podcast segment (183 fans, 2021–2026), plus
fans who appeared on the HBO travel show "Conan Must Go" (13 fans, 2 seasons).

See docs/STAKEHOLDERS.md for the full audience brief (Fans, Team Coco, HBO,
Distributors). See docs/DECISIONS.md for all technical decisions already made —
don't re-litigate those.

─── THE PROBLEM WITH THE CURRENT STRUCTURE ──────────────────────────────────

Everything is tangled together in two files:
  - All 183 fan records are hardcoded in generate_map.py as Python tuples
  - The JS, CSS, and HTML are all in one 1,700-line generated output file
  - Adding a new fan requires editing Python and rerunning a script
  - Improving the UI means editing a giant generated HTML blob
  - There's no dev server, no live reload, no way to preview quickly
  - Geocoding, country logic, RICH data, and build logic are all mixed together
    with no separation of concerns

─── WHAT I WANT YOU TO DO ───────────────────────────────────────────────────

Propose a clean project structure FIRST. Do not write any code yet.
Think like a senior engineer whose priorities are:
  (a) a new fan episode addable in under 2 minutes
  (b) UI changes fast to make and preview
  (c) output stays a single self-contained HTML file deployable anywhere

Target structure:

DATA LAYER
  data/episodes.csv      — one row per fan, editable in Excel/Numbers/Sheets
                           columns: date, uuid, mustGo, mustGoSeason, title,
                           name, location, occupation, topic
  data/rich_data.json    — keyed by episode title: highlights[], fanQuestion
                           editable without touching any Python
  data/geocache.json     — cached {location: [lat, lng]} so geocoding isn't
                           recomputed every build

BUILD LAYER
  build.py               — lean orchestrator: reads CSV + JSON, geocodes missing
                           locations, renders template, writes dist/
                           runs in <3 seconds
  lib/geocode.py         — geocoding logic and cache management
  lib/countries.py       — country/continent mapping + flag emoji lookup
  lib/highlights.py      — highlight generation (RICH lookup + 1-line fallback)

TEMPLATE LAYER
  template.html          — Jinja2 HTML skeleton with {{FANS_JSON}} injection
                           clean and readable — no generated content lives here
  src/map.js             — Leaflet map init, markers, popup builder
  src/charts.js          — Chart.js (4 charts)
  src/table.js           — episode table: search, filter, sort, render
  src/styles.css         — all CSS

OUTPUT
  dist/conan-fan-map.html — single self-contained file, CSS+JS inlined at
                            build time, droppable anywhere

DEV WORKFLOW
  python build.py --watch   rebuilds on any src/ or data/ file change
  python build.py --serve   localhost:8000 with auto-refresh
  Adding a fan = add one CSV row, run build, done.

─── TECHNICAL CONSTRAINTS — DO NOT CHANGE THESE ─────────────────────────────

  - Output must remain a single self-contained HTML file
  - Leaflet + CartoDB dark tiles + MarkerCluster (CDN links, no npm)
  - Chart.js (CDN, no npm)
  - Dark theme — exact CSS variables must be preserved:
      --orange:      #F26522   (TeamCoco orange)
      --mustgo:      #0057B8   (HBO blue)
      --bg:          #111318
      --bg2:         #181c24
      --bg3:         #1e2436
  - scrollWheelZoom: true on the map (Google Maps-style)
  - noWrap: true on tile layer (prevents world duplication — do not remove)
  - Date parsing: always new Date(f.date + 'T12:00:00') — never bare ISO string
  - Canada check in country classification must precede US state checks
    (", ca" substring appears in "ontario, canada" — see docs/DECISIONS.md)
  - Popup: maxWidth 640px, overflow-y: auto, max-height: 70vh
  - Must Go fans: HBO blue pin #0057B8, season badge "Must Go — S1/S2"
  - Location column: city + state/province + country flag emoji (flagLoc fn)
  - Platform logo buttons use inline base64 SVG — no external image URLs
  - Stats bar: Fans Featured, Countries, Must Go Guests, % World Nations
    (no "Fan Episodes" card — removed as redundant)
  - Analytics charts order: Top Countries → Continents → Occupations → Over Time
  - Appearances filter options: "All" / "Podcast" / "Conan Must Go (HBO)"
  - teamcocoUrl generated from make_slug(title) — verify apostrophe handling

─── NEW FEATURES TO BUILD (in priority order) ────────────────────────────────

After the refactor is working and verified, implement these one at a time.
Show me each feature before moving to the next.

  1. Shareable pin URLs
     - Opening any popup updates the browser URL to ?fan=episode-slug
     - On page load, if ?fan= param exists, fly to that pin and open its popup
     - Enables fans to share their specific pin on social media

  2. Find a fan near me
     - Button in the map legend or filter bar
     - Uses browser Geolocation API to get user coordinates
     - Flies to the nearest fan pin and opens its popup

  3. Embed mode
     - ?embed=1 hides header, stats bar, analytics section, footer, filter bar
     - Leaves only the map visible — clean for iframe embedding on teamcoco.com
     - Must be responsive and fill its container

  4. Export analytics PNG
     - One button in the analytics section
     - Uses html2canvas or equivalent to screenshot just the charts grid
     - Downloads as "conan-fan-map-analytics.png"
     - Key use case: distributors and Team Coco social media

  5. Mobile bottom sheet
     - On screens < 768px wide, replace the Leaflet popup with a slide-up sheet
     - Sheet covers ~60% of screen height from the bottom
     - Map stays visible and interactive above the sheet
     - Dismiss by tapping the map or a close button

  6. Choropleth layer toggle
     - A toggle button on the map adds a semi-transparent country fill layer
     - Countries shaded by fan count (lightest = 1, darkest = most)
     - Useful for Team Coco and HBO showing global reach
     - Leaflet GeoJSON layer using a free world countries GeoJSON source

  7. Expandable question column
     - In the episode table, the Fan's Question cell shows truncated text
     - Clicking the cell expands it inline to show the full question
     - Clicking again collapses it

─── EXECUTION ORDER ─────────────────────────────────────────────────────────

  1. Propose the directory structure — wait for my approval
  2. Migrate data: EPISODES → episodes.csv, RICH → rich_data.json, GEO → geocache.json
  3. Build lib/ modules (geocode, countries, highlights)
  4. Write build.py with --watch and --serve flags
  5. Split src/ files (styles.css, map.js, charts.js, table.js)
  6. Write template.html
  7. Run build, open in browser, verify output matches current conan-fan-map.html visually
  8. Implement new features one at a time, showing me each before moving on

Run the build and confirm it works before each step.
Never skip the visual verification step — pixel-level fidelity to the current
output is required before adding new features.
```

---

## Notes for Using This Prompt

**When to use it:** At the start of a fresh Claude Code session in your project directory.

**What to have ready:**
- `conan-fan-map.html` in the working directory
- `generate_map.py` in the working directory
- This `docs/` folder in the working directory
- Python 3.8+ with `pip install jinja2 watchdog` available

**After approval of the structure:** Claude Code should execute steps 1–7 before
touching any new features. Don't let it skip the visual verification step.

**Adding the very first new fan post-refactor:**
```bash
# 1. Add a row to data/episodes.csv
# 2. Run:
python build.py
# Done. dist/conan-fan-map.html is updated.
```

**If something breaks during refactor:** The original `conan-fan-map.html` and
`generate_map.py` are the ground truth. The refactored build must produce
byte-for-byte equivalent fan data (same 183 fans, same coordinates, same countries).
Run a diff check on the FANS JSON before/after to verify.
