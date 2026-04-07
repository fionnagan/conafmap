"""Highlight generation, slug creation, and Must Go season lookup."""

import re
import unicodedata

TEAMCOCO_BASE = 'https://teamcoco.com/podcasts/conan-obrien-needs-a-friend/episodes/'

MUST_GO_SEASONS = {
    'Conan Must Go: Anna (Thailand)':       1,
    'Conan Must Go: Jarle (Norway)':        1,
    'Conan Must Go: Kai (Norway)':          1,
    'Conan Must Go: Whitney (Thailand)':    1,
    'Conan Must Go: Matias (Argentina)':    1,
    'Conan Must Go: Sebastian (Argentina)': 1,
    'Conan Must Go: Mohammed (Ireland)':    1,
    'Conan Must Go: Cami (Argentina)':      1,
    'The Life Of Reilly':                   2,
    'Slush Metal':                          2,
    "Don't Sit Under The Walnut Tree":      2,
    'The Last DVD Store':                   2,
    "It's An Honor Just To Be Engaged":     2,
}


def make_slug(title):
    """Convert episode title to teamcoco.com URL slug."""
    t = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii')
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s-]", '', t)
    t = re.sub(r'\s+', '-', t.strip())
    t = re.sub(r'-+', '-', t)
    return t


def make_highlights(name, location, occupation, topic, title, rich_data):
    """
    Return (highlights_list, fan_question_str, conan_response_str).
    Uses rich_data dict if available; otherwise generates a single
    contextual line from topic, or nothing.
    """
    entry = rich_data.get(f'{title}|{name}') or rich_data.get(title)
    if entry:
        return (
            entry.get('highlights', []),
            entry.get('fanQuestion', ''),
            entry.get('conanResponse', ''),
        )

    topic = (topic or '').strip().rstrip('.')
    job = occupation.strip().rstrip('.').lower()

    if topic and topic.lower() != job and len(topic) > len(job) + 5:
        return [f'{name} joined Conan to talk about {topic}'], '', ''

    return [], '', ''
