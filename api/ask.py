"""
api/ask.py — Fan-facing Q&A endpoint for the Conan Fan Map.

POST /api/ask  {"question": "who's the fan from Norway?"}
  → {"answer": "..."}

Reads api/fans_context.json (fan facts, emitted by build.py), passes them as
context to Claude Haiku, and returns a short answer. Facts only — no transcripts.

Guards (v1 cost/abuse posture; the real backstop is the Anthropic Console spend cap):
  - same-origin check (Origin/Referer host must match the request Host)
  - request-body size cap + question-length cap
  - max_tokens cap on the response, Haiku model
  - system prompt scopes Claude to the dataset and refuses off-topic asks
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import json
import os
import urllib.request
import datetime

# Haiku pricing (per million tokens, as of 2025)
_INPUT_COST_PER_M  = 0.80
_OUTPUT_COST_PER_M = 4.00
# Prompt-caching multipliers on the base input price:
#   cache write (5-min TTL) = 1.25x, cache read = 0.10x
_CACHE_WRITE_PER_M = _INPUT_COST_PER_M * 1.25   # 1.00
_CACHE_READ_PER_M  = _INPUT_COST_PER_M * 0.10   # 0.08
_NOTION_DB_ID      = 'eb5f321bf43246ef9369bf012343766a'
_NOTION_API        = 'https://api.notion.com/v1/pages'

# Human-readable explanations for each error code logged to Notion
_ERROR_REASONS = {
    403: "Same-origin check failed — request did not come from the website (likely a direct API call, bot, or scraper).",
    413: "Request body exceeded the 2 KB size limit — question was too long or payload was malformed.",
    400: "Bad request — either the body was not valid JSON or the question field was empty.",
    500: "Anthropic API key not found in Vercel environment variables — the service is misconfigured.",
    502: "Upstream Claude API error — the call to Anthropic failed.",
}


def _parse_ua(ua):
    """Return (device_type, browser_string) from a User-Agent string."""
    import re
    ua = ua or ''
    if re.search(r'(?i)(tablet|ipad)', ua):
        device = 'Tablet'
    elif re.search(r'(?i)(mobile|android|iphone|ipod|blackberry|windows phone)', ua):
        device = 'Mobile'
    else:
        device = 'Desktop'
    for name, pattern in [
        ('Edge',    r'Edg(?:e)?/(\S+)'),
        ('Chrome',  r'(?:Chrome|CriOS)/(\S+)'),
        ('Firefox', r'(?:Firefox|FxiOS)/(\S+)'),
        ('Safari',  r'Version/(\S+).*Safari'),
        ('Samsung', r'SamsungBrowser/(\S+)'),
    ]:
        m = re.search(pattern, ua)
        if m:
            return device, f'{name}/{m.group(1).split(".")[0]}'
    return device, 'Other'


def _get_client_info(headers):
    """Extract IP, location string, device type, and browser from request headers."""
    ip = (headers.get('X-Forwarded-For') or headers.get('X-Real-IP') or '').split(',')[0].strip()
    city    = headers.get('X-Vercel-Ip-City', '')
    country = headers.get('X-Vercel-Ip-Country', '')
    location = ', '.join(filter(None, [city, country]))
    device, browser = _parse_ua(headers.get('User-Agent', ''))
    return ip, location, device, browser


def _log(question, answer='', usage=None, status='Success', error_reason='',
          ip='', location='', device='', browser='', cached=False):
    """POST a Q&A row to Notion. Called synchronously before the response is sent.

    Cache-aware cost: with prompt caching the SDK reports input in three buckets —
    `input_tokens` (fresh, full price), `cache_creation_input_tokens` (written to
    cache, 1.25x) and `cache_read_input_tokens` (read from cache, 0.10x). A response
    served from the KV response cache (cached=True) costs nothing.
    """
    token = os.environ.get('NOTION_TOKEN') or os.environ.get('NotionCONAFmap', '')
    if not token:
        return
    fresh_in   = getattr(usage, 'input_tokens', 0) if usage else 0
    output_tok = getattr(usage, 'output_tokens', 0) if usage else 0
    cache_write = getattr(usage, 'cache_creation_input_tokens', 0) if usage else 0
    cache_read  = getattr(usage, 'cache_read_input_tokens', 0) if usage else 0
    # "Input Tokens" in Notion = total input seen by the model (meaningful number);
    # cost reflects the per-bucket cache discounts.
    input_tok = fresh_in + cache_write + cache_read
    cost_usd  = 0.0 if cached else round(
        (fresh_in    * _INPUT_COST_PER_M +
         cache_write * _CACHE_WRITE_PER_M +
         cache_read  * _CACHE_READ_PER_M +
         output_tok  * _OUTPUT_COST_PER_M) / 1_000_000,
        6
    )
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
    payload = json.dumps({
        'parent': {'database_id': _NOTION_DB_ID},
        'properties': {
            'Question':     {'title':     [{'text': {'content': question[:2000]}}]},
            'Answer':       {'rich_text': [{'text': {'content': answer[:2000]}}]},
            'Timestamp':    {'date':      {'start': ts, 'time_zone': 'UTC'}},
            'Status':       {'select':    {'name': status}},
            'Error Reason': {'rich_text': [{'text': {'content': error_reason[:500]}}]},
            'Input Tokens': {'number': input_tok},
            'Output Tokens':{'number': output_tok},
            'Est Cost USD': {'number': cost_usd},
            'IP':           {'rich_text': [{'text': {'content': ip[:100]}}]},
            'Location':     {'rich_text': [{'text': {'content': location[:100]}}]},
            'Device':       {'rich_text': [{'text': {'content': device}}]},
            'Browser':      {'rich_text': [{'text': {'content': browser}}]},
        }
    }).encode('utf-8')
    try:
        req = urllib.request.Request(
            _NOTION_API, data=payload,
            headers={
                'Content-Type':   'application/json',
                'Authorization':  'Bearer ' + token,
                'Notion-Version': '2022-06-28',
            }, method='POST'
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # never let logging failure affect the user response


CONTEXT_FILE     = Path(__file__).parent / 'fans_context.json'
MAX_BODY_BYTES   = 2000
MAX_QUESTION_LEN = 500
MAX_TOKENS       = 600
MODEL            = 'claude-haiku-4-5'

SYSTEM_TEMPLATE = """You are the Q&A assistant for the Conan Fan Map — an interactive map of fans \
who appeared on "Conan O'Brien Needs a Fan" (podcast) and "Conan Must Go" (HBO show).

== PRE-COMPUTED STATS (use these for count questions — do NOT recount from the fan list) ==
{stats}

== FAN LIST (one line per fan) ==
date | name | location | country | occupation | episode | topic | Must Go season (or "-")
{table}

Rules:
- Answer questions about these fans only. Decline off-topic questions politely.
- Be concise and friendly — 1–4 sentences or a short list. This shows on a fan website.
- For COUNT questions (e.g. "how many from X?"): read the number directly from PRE-COMPUTED STATS above. \
State it once, confidently. Never recount, never self-correct mid-response.
- For NAME/DETAIL questions: look up the fan in the list and answer directly.
- Always give a complete answer. Never end with "Would you like me to..." or offer follow-up options — \
just include the full information in your response.
- Do not invent fans or details not in the data."""


def _load_facts():
    with open(CONTEXT_FILE, encoding='utf-8') as f:
        return json.load(f)


def _build_stats(facts):
    from collections import Counter
    country_counts  = Counter(f['country']  for f in facts if f.get('country'))
    category_counts = Counter(f['category'] for f in facts if f.get('category'))
    total    = len(facts)
    must_go  = sum(1 for f in facts if f.get('mustGo'))
    # Named countries only (exclude the "Unknown" bucket) for the represented set.
    represented = sorted(c for c in country_counts if c and c != 'Unknown')
    lines = [
        f"Total fans: {total}",
        f"Conan Must Go guests: {must_go}",
        f"Podcast-only fans: {total - must_go}",
        "",
        # Counts only — the per-fan names live in the FAN LIST below, so listing
        # them here too is pure duplication. Keeping just the counts preserves the
        # counting fix while shrinking the cached prompt.
        "Fans by country (count):",
    ]
    for country, count in country_counts.most_common():
        lines.append(f"  {country}: {count}")
    lines += ["", "Fans by occupation category (count):"]
    for cat, count in category_counts.most_common():
        lines.append(f"  {cat}: {count}")
    lines += [
        "",
        f"Countries represented ({len(represented)}): {', '.join(represented)}.",
        "There are 193 UN member states. When asked which countries are NOT "
        "represented, you may compute and list them by subtracting the represented "
        "set above from the world's countries — give a complete answer, don't decline.",
    ]
    return '\n'.join(lines)


def _build_system_prompt(facts):
    stats = _build_stats(facts)
    lines = []
    for f in facts:
        season = f"S{f['season']}" if f.get('mustGo') and f.get('season') else '-'
        lines.append(
            f"{f['date']} | {f['name']} | {f['location']} | {f.get('country','')} | "
            f"{f['occupation']} | {f['episode']} | {f['topic']} | {season}"
        )
    return SYSTEM_TEMPLATE.format(stats=stats, table='\n'.join(lines))


# The system prompt is identical for every request (it changes only when
# fans_context.json is rebuilt). Build it once per warm lambda so the text is
# byte-identical across requests — a hard requirement for prompt-cache hits.
_SYSTEM_CACHE = None


def _system_prompt():
    global _SYSTEM_CACHE
    if _SYSTEM_CACHE is None:
        _SYSTEM_CACHE = _build_system_prompt(_load_facts())
    return _SYSTEM_CACHE


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        ip, location, device, browser = '', '', '', ''

        # 1. Same-origin guard — browser must send Origin/Referer matching our Host.
        if not self._is_same_origin():
            ip, location, device, browser = _get_client_info(self.headers)
            _log('(no question — blocked before parse)', status='Error',
                 error_reason=_ERROR_REASONS[403],
                 ip=ip, location=location, device=device, browser=browser)
            return self._send(403, {'error': 'forbidden'})

        ip, location, device, browser = _get_client_info(self.headers)

        # 2. Body size cap.
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            _log('(no question — body too large)', status='Error',
                 error_reason=_ERROR_REASONS[413],
                 ip=ip, location=location, device=device, browser=browser)
            return self._send(413, {'error': 'request too large'})

        # 3. Parse JSON body.
        try:
            payload = json.loads(self.rfile.read(length))
            question = str(payload.get('question', '')).strip()
        except Exception:
            _log('(no question — invalid JSON)', status='Error',
                 error_reason=_ERROR_REASONS[400],
                 ip=ip, location=location, device=device, browser=browser)
            return self._send(400, {'error': 'invalid JSON'})

        if not question:
            _log('(empty)', status='Error',
                 error_reason=_ERROR_REASONS[400],
                 ip=ip, location=location, device=device, browser=browser)
            return self._send(400, {'error': 'empty question'})
        question = question[:MAX_QUESTION_LEN]

        # 4. Key must be configured.
        api_key = (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('CLAUDE')
                   or os.environ.get('Anthropic_API', ''))
        if not api_key:
            _log(question, status='Error',
                 error_reason=_ERROR_REASONS[500],
                 ip=ip, location=location, device=device, browser=browser)
            return self._send(500, {'error': 'service not configured'})

        # 5. Call Claude. The system prompt is sent as a single cached block —
        #    Anthropic caches the ~7.5K-token prefix (5-min TTL) so repeat calls
        #    pay 0.10x for it instead of full price. cache_control marks the cut.
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[{
                    'type': 'text',
                    'text': _system_prompt(),
                    'cache_control': {'type': 'ephemeral'},
                }],
                messages=[{'role': 'user', 'content': question}],
            )
            answer = ''.join(b.text for b in msg.content if b.type == 'text').strip()
            _log(question, answer=answer, usage=msg.usage, status='Success',
                 ip=ip, location=location, device=device, browser=browser)
            return self._send(200, {'answer': answer})
        except Exception as exc:
            reason = f"{_ERROR_REASONS[502]} Detail: {type(exc).__name__}: {exc}"
            _log(question, status='Error', error_reason=reason[:500],
                 ip=ip, location=location, device=device, browser=browser)
            return self._send(502, {'error': 'upstream error'})

    def _is_same_origin(self):
        origin = self.headers.get('Origin') or self.headers.get('Referer') or ''
        if not origin:
            return False
        origin_host = urlparse(origin).netloc.lower()
        host = (self.headers.get('Host') or '').lower()
        return bool(origin_host) and origin_host == host

    def _send(self, code, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # suppress default request logging
