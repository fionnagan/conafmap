# Technical & Design Decisions

Every significant decision made during this project, with the rationale.
Use this to avoid re-litigating solved problems in Claude Code.

---

## Architecture

### Single self-contained HTML file (not a multi-file web app)
**Decision:** The output is always one `.html` file with all CSS, JS, and data inlined.
**Rationale:** Can be emailed, dropped on any web server, embedded in an iframe,
or opened directly from the filesystem with no build step by the end user.
Team Coco staff don't run a dev server — they just open a file.

### Python build script, not Node/Webpack/Vite
**Decision:** `generate_map.py` is the only build tool.
**Rationale:** Team Coco staff are more likely to have Python than Node. The script
has zero npm dependencies and runs in under 3 seconds.

### Data hardcoded in Python, not fetched from an API
**Decision:** All 183 fan records live in `generate_map.py` as tuples.
**Rationale:** There is no backend. The podcast RSS feed doesn't include fan metadata.
All data was manually curated from episode transcripts, the TeamCoco RSS, and the
Conan Must Go episodes. A future refactor should move this to `episodes.csv`.

---

## Map

### Leaflet.js + CartoDB Dark tiles
**Decision:** Leaflet with `https://{s}.basemaps.cartocdn.com/dark_all/` tiles.
**Rationale:** Free, no API key required, dark theme matches the page aesthetic,
and CartoDB tiles render well at all zoom levels for a global map.

### MarkerCluster (not individual pins at low zoom)
**Decision:** Using `Leaflet.markercluster` plugin.
**Rationale:** 183 pins at zoom level 2 is unreadable without clustering. Clusters
show a count badge and spiderfy on click.

### World-wrap disabled (`noWrap: true`)
**Decision:** `noWrap: true` on the tile layer + `maxBounds: [[-90,-180],[90,180]]`.
**Rationale:** Without this, Leaflet renders infinite horizontal copies of the map.
Markers placed near the antimeridian (New Zealand, Pacific fans) appear on ghost
map copies and pin-click behavior breaks. This is a known Leaflet issue.

### Scroll-wheel zoom enabled
**Decision:** `scrollWheelZoom: true`.
**Rationale:** The user explicitly requested Google Maps-style scroll zoom. The map
is the primary interaction surface; disabling scroll zoom made it feel unresponsive.

### Popup width: 640px min 520px
**Decision:** `maxWidth: 640, minWidth: 520` in `bindPopup()` options, plus
`max-width: 640px !important` in CSS, and `max-height: 70vh; overflow-y: auto`
on `.popup-inner`.
**Rationale:** Narrower popups (previous: 360px, then 480px) cut off the Simplecast
audio player iframe and made the highlights unreadable. The popup also needs to scroll
vertically when the map container isn't tall enough to show the full content.

---

## Colors & Branding

### TeamCoco orange `#F26522` for fan pins
**Decision:** `--orange: #F26522` is the primary accent color throughout.
**Rationale:** This is TeamCoco's brand orange, used on teamcoco.com and in their
show graphics. Fans associate this color with the brand.

### HBO blue `#0057B8` for Must Go pins and badges
**Decision:** `--mustgo: #0057B8` replaces the original red/pink `#e94560`.
**Rationale:** "Conan Must Go" is an HBO product. The red/pink color had no brand
meaning. HBO's classic deep royal blue (`#0057B8`) clearly signals the HBO connection
and is visible on the dark map tiles. This color is used consistently: pin icon,
popup badge, table badge, legend dot, chart palette.

### Dark theme with `#111318` base
**Decision:** Dark background throughout, not light mode.
**Rationale:** Maps look dramatically better on dark backgrounds (geographic features
are clearer, pins pop). The CartoDB dark tile set is specifically designed for this.
The aesthetic also aligns with the late-night / podcast mood of the show.

---

## Location Display

### Formatted display locations separate from geocoding locations
**Decision:** Two separate fields: `location` (raw, used for geocoding) and
`displayLocation` (formatted "City, ST — Country", stripped to "City, ST 🇨🇦" in UI).
**Rationale:** Geocoding uses exact string matching against the `GEO` dict.
Changing "Toronto, Canada" to "Toronto, ON — Canada" for display would break the
geocoding lookup. The two fields serve different purposes.

### Country flag emoji in table, not "— Country" text
**Decision:** `flagLoc(f)` function strips the "— Country" suffix and appends the
Unicode flag emoji (e.g. `🇺🇸`, `🇨🇦`, `🇳🇴`).
**Rationale:** Flag emojis are more compact, visually scannable, and internationally
recognizable than country name text. The table is already dense; removing 6–12
characters per row reduces visual noise significantly.

### Canada check before US in `country_from_location()`
**Decision:** The Canada block is checked before the US state-code block.
**Rationale:** The string `", ca"` (California abbreviation) is a substring of
`"ontario, canada"`. The original code checked US state codes first, causing every
Ontario/Canada location to be misclassified as United States. Moving Canada first
fixes this. Do not reorder these checks.

---

## Data Quality

### Generic highlights replaced with nothing (or 1 line max)
**Decision:** `make_highlights()` returns `[]` when no real data exists in `RICH`.
If `about_topic` is meaningfully different from `occupation`, it returns 1 line.
**Rationale:** The old template generated 3 formulaic lines for every fan
("X talked with Conan about Y / Working as a Y, X gave Conan a window into..."
/ "Conan had plenty of follow-up questions..."). These were identical in structure
across 170+ fans and made the popup feel machine-generated and useless.
Real data (RICH dict) is used where available; silence is better than filler.

### `about_topic` as 8th tuple field
**Decision:** EPISODES tuples optionally have an 8th field `about_topic` describing
the conversation topic.
**Rationale:** For many fans, the occupation (e.g. "Conservation Authority Worker")
doesn't describe what was interesting about the episode (monitoring polar bears).
The 8th field captures this nuance and appears in the Fan's Question column as a
fallback when no formal question text is available.

### Fan question vs. topic distinction
**Decision:** `fanQuestion` = the literal question the fan asked Conan at the end of
the segment. `topic` = what the conversation was about.
**Rationale:** These are different things. The "Needs a Fan" format has a specific
moment where the fan gets to ask Conan one personal question. The topic is the bulk
of the conversation. Both are stored; the table shows whichever is available.

---

## Stats Bar

### Removed "Fan Episodes" count card
**Decision:** The `statEpisodes` card was removed.
**Rationale:** It showed 183, identical to "Fans Featured." One fan = one episode
appearance, so the two cards were always identical. Redundant information reduces
the signal value of the stats bar.

---

## Header & Platform Links

### Inline SVG logos (no external image URLs)
**Decision:** All platform logos (Apple Podcasts, Spotify, Amazon Music, SiriusXM)
are base64-encoded SVG data URIs embedded directly in the HTML.
**Rationale:** External image URLs (even Wikimedia) are unreliable — images move,
become unavailable, or return the wrong version. The previous implementation used
a Wikimedia URL for Apple Podcasts that returned the old macOS icon, not the
current purple gradient iOS icon the user wanted. Inline SVGs have zero dependencies
and load instantly.

---

## Build Pipeline

### `teamcocoUrl` generated from episode title slug
**Decision:** URLs like `https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes/interrupto`
are generated by `make_slug(title)` which lowercases, strips non-alphanumeric, and
joins with hyphens.
**Rationale:** The TeamCoco website uses a consistent slug format. This avoids
maintaining a manual URL for every episode. However, slugs should be spot-checked
manually for titles with apostrophes, punctuation, or special characters.

### `mustGoSeason` derived from `MUST_GO_SEASONS` lookup dict
**Decision:** A dict maps episode title → season number (1 or 2). Entries not in the
dict get `mustGoSeason: 0`.
**Rationale:** Clean separation between "is this fan a Must Go fan" (the `mustGo`
boolean) and "which season" (the `mustGoSeason` int). This allows season-specific
filtering or styling in the future without changing the data schema.
