# Conan Fan Map — Claude Code Project Context

> This file is the single source of truth for picking up this project in Claude Code.
> Read it fully before touching any file. Companion docs live in `docs/`.

---

## What This Project Is

An interactive world map of every fan who has appeared on the **"Conan O'Brien Needs a Fan"**
podcast segment (183 fans, 2021–2026) and the HBO travel show **"Conan Must Go"** (13 fans,
2 seasons). Built as a single self-contained HTML file deployable anywhere.

**Live deliverable:** `conan-fan-map.html` (in this folder / `dist/` after refactor)
**Build script:** `generate_map.py` (reads hardcoded data, writes HTML)

See `docs/STAKEHOLDERS.md` for the full audience brief.
See `docs/REFACTOR_PROMPT.md` for the ready-to-use refactor prompt.

---

## Current File State

```
outputs/
├── conan-fan-map.html      # The built output — ~1,700 lines, single self-contained file
├── generate_map.py         # Python build script — ~850 lines, all data hardcoded inside
├── CLAUDE.md               # ← you are here
└── docs/
    ├── DECISIONS.md        # Every technical and design decision with rationale
    ├── DATA_GUIDE.md       # How to add/edit fan episode data
    ├── STAKEHOLDERS.md     # Audience briefs (Fans, Team Coco, HBO, Distributors)
    └── REFACTOR_PROMPT.md  # The full Claude Code refactor prompt, ready to paste
```

**The project has not yet been refactored.** The recommended next step is to run the
refactor prompt in `docs/REFACTOR_PROMPT.md`, which will split this into a proper
`src/` + `data/` + `build.py` structure. Get my approval on the proposed structure
before writing any code.

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

See `docs/DATA_GUIDE.md` for the full guide. Quick version:

1. Add a tuple to `EPISODES` in `generate_map.py` (8-field format preferred):
   ```python
   ("2026-04-10", "simplecast-uuid-here", False,
    "Episode Title", "FanName", "City, State", "Occupation",
    "what they talked about with Conan"),
   ```
2. If the location is new, add it to `GEO` dict with `[lat, lng]`
3. If the location display needs formatting, add to `DISPLAY_LOC` dict
4. Optionally add real highlights + fan question to `RICH` dict
5. Run `python3 generate_map.py` — output is `conan-fan-map.html`

---

## Refactor Target Architecture

The recommended refactor splits everything into:

```
conan-fan-map/
├── data/
│   ├── episodes.csv          # source of truth — one row per fan
│   ├── rich_data.json        # highlights + fan questions keyed by episode title
│   └── geocache.json         # cached coordinates
├── src/
│   ├── styles.css
│   ├── map.js
│   ├── charts.js
│   └── table.js
├── lib/
│   ├── geocode.py
│   ├── countries.py
│   └── highlights.py
├── template.html             # Jinja2 skeleton
├── build.py                  # python build.py --watch / --serve
└── dist/
    └── conan-fan-map.html    # built output
```

Use the full prompt in `docs/REFACTOR_PROMPT.md`. **Propose structure, wait for approval,
then execute step by step.**
