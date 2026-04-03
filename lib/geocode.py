"""Geocoding: cache lookup first, Nominatim fallback, cache persistence."""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

CACHE_PATH = Path(__file__).parent.parent / 'data' / 'geocache.json'

# Fallback coordinates used when nothing else works (geographic centre of USA)
FALLBACK_COORDS = [39.83, -98.58]


def load_cache():
    """Return the geocache dict, keyed by location string."""
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Persist the geocache dict to disk."""
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _nominatim(location):
    """Query Nominatim for coordinates. Returns [lat, lng] or None."""
    q = urllib.parse.quote(location)
    url = f'https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1'
    req = urllib.request.Request(url, headers={'User-Agent': 'ConanFanMap/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if data:
            return [float(data[0]['lat']), float(data[0]['lon'])]
    except Exception:
        pass
    return None


def geo(location, cache, verbose=False):
    """
    Return [lat, lng] for a location string.
    Checks cache first (exact then partial), then queries Nominatim,
    then falls back to country or FALLBACK_COORDS.
    Updates cache in-place when a new result is fetched.
    """
    # Exact match
    if location in cache:
        return cache[location]

    # Case-insensitive exact
    loc_l = location.lower()
    for k, v in cache.items():
        if k.lower() == loc_l:
            cache[location] = v
            return v

    # Partial match against cache keys
    for k, v in cache.items():
        if k.lower() in loc_l or loc_l in k.lower():
            return v

    # Try first part of a comma-split location
    parts = location.split(',')
    if len(parts) > 1:
        simple = parts[0].strip()
        if simple in cache:
            return cache[simple]

    # Nominatim fallback
    if verbose:
        print(f'  [geocode] querying Nominatim for: {location!r}')
    coords = _nominatim(location)
    if coords:
        cache[location] = coords
        if verbose:
            print(f'  [geocode] found {coords}')
        time.sleep(1.1)  # Nominatim rate-limit: 1 req/sec
        return coords

    if verbose:
        print(f'  [geocode] not found, using fallback')
    return FALLBACK_COORDS
