# Data Guide — How to Add & Edit Fan Episodes

This guide covers everything needed to add a new fan, fix existing data,
or understand how the data pipeline works.

---

## Source of Truth (Current State)

All fan data lives in **`generate_map.py`** as Python tuples in the `EPISODES` list.
After the planned refactor, this moves to **`data/episodes.csv`** (see end of this doc).

---

## Adding a New Fan Episode

### Step 1 — Add to EPISODES list

Open `generate_map.py` and find the `EPISODES` list. Add a new tuple in date order
(newest at top). Use the **8-field format** whenever possible:

```python
("YYYY-MM-DD", "simplecast-uuid", mustGo, "Episode Title",
 "FanFirstName", "City, State/Province", "Occupation",
 "brief description of what they talked about with Conan"),
```

**Field reference:**

| # | Field | Example | Notes |
|---|-------|---------|-------|
| 1 | `date` | `"2026-05-01"` | ISO 8601. Use `T12:00:00` fix is in JS, not needed here |
| 2 | `uuid` | `"52d4744c-..."` | Simplecast episode UUID. Found in the RSS feed or episode URL. Use `""` if unknown |
| 3 | `mustGo` | `False` | Python bool (capital F/T). `True` = appeared on HBO show |
| 4 | `title` | `"Grand Theft Rickshaw"` | Exact episode title — used as key for RICH dict and slug generation |
| 5 | `name` | `"Rusty"` | Fan's first name only |
| 6 | `location` | `"Auckland"` | See location rules below |
| 7 | `occupation` | `"Rickshaw Driver"` | Fan's job/role |
| 8 | `about_topic` | `"navigating Auckland by rickshaw"` | What they discussed. Omit if same as occupation |

**If the fan is Must Go, also add to `MUST_GO_SEASONS`:**
```python
MUST_GO_SEASONS = {
    ...
    "Episode Title Here": 1,   # or 2
}
```

### Step 2 — Add location to GEO dict (if new)

If the location string is new (not already in `GEO`), add it:

```python
GEO = {
    ...
    "Auckland": [-36.87, 174.77],
}
```

Find coordinates at: [latlong.net](https://www.latlong.net) or Google Maps
(right-click → "What's here?").

**Location string rules:**
- Use the most specific place name that makes sense (city > state > country)
- US locations: `"City, ST"` (e.g. `"Austin, TX"`) or just `"City"` if well-known
- Canadian locations: `"City, Province"` or `"City, Canada"` (e.g. `"Toronto, Canada"`)
- International: just the city or region name (e.g. `"Bergen, Norway"` or `"Bergen"`)
- Avoid putting the country in the location string for non-English-speaking cities
  (geocoding uses the string as a lookup key, not for display)

### Step 3 — Add display location (if new)

Add the formatted display string to `DISPLAY_LOC` dict:

```python
DISPLAY_LOC = {
    ...
    "Auckland": "Auckland — New Zealand",
}
```

Format: `"City, State/Province — Country"` where applicable.
The `flagLoc()` JS function will strip `" — Country"` and append the flag emoji.

**Examples:**
- `"Toronto, ON — Canada"` → displays as `"Toronto, ON 🇨🇦"`
- `"Miami, FL — USA"` → displays as `"Miami, FL 🇺🇸"`
- `"Bergen — Norway"` → displays as `"Bergen 🇳🇴"`
- `"Singapore"` → displays as `"Singapore 🇸🇬"` (flag added directly)

### Step 4 — Add rich data (optional but preferred)

If you have real highlights or the fan's question, add to the `RICH` dict:

```python
RICH = {
    ...
    "Episode Title Here": {
        "highlights": [
            "A genuinely interesting thing that happened in the episode",
            "Another specific moment worth noting",
            "A funny or memorable quote or exchange",
        ],
        "fanQuestion": "The specific question the fan asked Conan at the end",
    },
}
```

**Guidelines for highlights:**
- 1–3 items. 3 is ideal; 1 is fine; 0 (empty list `[]`) is better than generic filler.
- Be specific. "Rusty told Conan about X" is better than "They discussed transportation."
- Include direct quotes when memorable.
- Don't write `"X gave Conan a window into a world he knew nothing about"` — this was
  the old generic template and was removed for being useless.

**Fan question:**
- This is the literal question the fan asks Conan in the "fan question" segment.
- It's always personal/about Conan, not about the fan's job.
- Use `""` if you don't have it — the `topic` field fills in as fallback in the table.

### Step 5 — Rebuild

```bash
python3 generate_map.py
```

Output: `conan-fan-map.html` (updated in place).

---

## Finding the Simplecast UUID

The UUID appears in the episode's Simplecast player embed URL:
```
https://player.simplecast.com/52d4744c-4ca0-4848-ab38-154fd33fe32b?dark=true
```

You can also find it in the podcast RSS feed:
```
https://feeds.simplecast.com/dHoohVNH
```

For **Conan Must Go** episodes, most don't have a Simplecast UUID (they're HBO content,
not podcast episodes). Use `""` for these — the popup won't render a player, which is correct.

---

## Editing Existing Fan Data

| What to change | Where |
|----------------|-------|
| Fan name, date, location, occupation | `EPISODES` list in `generate_map.py` |
| Highlights or fan question | `RICH` dict in `generate_map.py` |
| Coordinates | `GEO` dict in `generate_map.py` |
| Formatted display location | `DISPLAY_LOC` dict in `generate_map.py` |
| Country classification | `country_from_location()` function in `generate_map.py` |
| Must Go season number | `MUST_GO_SEASONS` dict in `generate_map.py` |

After any change, run `python3 generate_map.py` to rebuild.

---

## Current Must Go Episode Roster

### Season 1 (8 fans)
| Fan | Location | Episode Title |
|-----|----------|---------------|
| Anna | Thailand | Conan Must Go: Anna (Thailand) |
| Jarle | Norway | Conan Must Go: Jarle (Norway) |
| Kai | Bergen, Norway | Conan Must Go: Kai (Norway) |
| Whitney | Thailand | Conan Must Go: Whitney (Thailand) |
| Matias | Argentina | Conan Must Go: Matias (Argentina) |
| Sebastian | Buenos Aires | Conan Must Go: Sebastian (Argentina) |
| Mohammed | Ireland | Conan Must Go: Mohammed (Ireland) |
| Cami | Argentina | Conan Must Go: Cami (Argentina) |

### Season 2 (5 fans)
| Fan | Location | Episode Title |
|-----|----------|---------------|
| Reilly | Hokitika, NZ | The Life Of Reilly |
| Katherina | Austria | Slush Metal |
| Muntasser | Austria | Don't Sit Under The Walnut Tree |
| James | Christchurch, NZ | The Last DVD Store |
| Penny | Christchurch, NZ | It's An Honor Just To Be Engaged |

---

## Episode Data as of Last Build

- **Total fans:** 183
- **Years covered:** 2021–2026
- **Countries:** 34
- **Date of last full audit:** April 2026 (via Cowork session)

### Finding New Episodes

1. **RSS feed:** `https://feeds.simplecast.com/dHoohVNH` — filter for episodes
   containing "Fan" in the title, or check the "Conan O'Brien Needs a Fan" tag
2. **TeamCoco website:** `https://teamcoco.com/podcasts/conan-obrien-needs-a-friend`
3. **Episode pattern:** Fan episodes are typically titled with a whimsical phrase
   unrelated to the fan's actual job (e.g. "Blueberry Jam" = fan is a urologist)

---

## After Refactor: CSV Format

Once refactored, `data/episodes.csv` will replace the `EPISODES` list.
Target column order:

```
date,uuid,mustGo,mustGoSeason,title,name,location,occupation,topic,highlights,fanQuestion
```

- `mustGo`: `TRUE` / `FALSE`
- `mustGoSeason`: `0`, `1`, or `2`
- `highlights`: pipe-separated `"Highlight one|Highlight two|Highlight three"`
- `fanQuestion`: plain text

This format is editable in Excel, Numbers, or Google Sheets.
`build.py` will read the CSV, apply geocoding (with cache), and generate the HTML.

---

## Country → Continent Mapping (for charts)

```python
regionAssign = {
  'United States':  'North America',
  'Canada':         'North America',
  'Mexico':         'North America',
  'United Kingdom': 'Europe',
  'Ireland':        'Europe',
  'Norway':         'Europe',
  'Netherlands':    'Europe',
  'Finland':        'Europe',
  'Austria':        'Europe',
  'Hungary':        'Europe',
  'Greece':         'Europe',
  'Croatia':        'Europe',
  'Slovenia':       'Europe',
  'Spain':          'Europe',
  'Portugal':       'Europe',
  'Ukraine':        'Europe',
  'Iceland':        'Europe',
  'India':          'Asia',
  'Philippines':    'Asia',
  'Thailand':       'Asia',
  'Singapore':      'Asia',
  'Kazakhstan':     'Asia',
  'Kyrgyzstan':     'Asia',
  'Lebanon':        'Asia',
  'Iran':           'Asia',
  'Israel':         'Asia',
  'Turkey':         'Asia',
  'Morocco':        'Africa',
  'Egypt':          'Africa',
  'Ethiopia':       'Africa',
  'Kenya':          'Africa',
  'Australia':      'Oceania',
  'New Zealand':    'Oceania',
  'Argentina':      'South America',
  'Brazil':         'South America',
  'Colombia':       'South America',
  'Antarctica':     'Antarctica',
}
```

Countries not in this map are simply excluded from the Continents chart.
