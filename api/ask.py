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
          ip='', location='', device='', browser=''):
    """POST a Q&A row to Notion. Called synchronously before the response is sent."""
    token = os.environ.get('NOTION_TOKEN') or os.environ.get('NotionCONAFmap', '')
    if not token:
        return
    input_tok  = getattr(usage, 'input_tokens', 0) if usage else 0
    output_tok = getattr(usage, 'output_tokens', 0) if usage else 0
    cost_usd   = round(
        input_tok  / 1_000_000 * _INPUT_COST_PER_M +
        output_tok / 1_000_000 * _OUTPUT_COST_PER_M,
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
    lines = [
        f"Total fans: {total}",
        f"Conan Must Go guests: {must_go}",
        f"Podcast-only fans: {total - must_go}",
        "",
        "Fans by country:",
    ]
    for country, count in country_counts.most_common():
        names = [f['name'] for f in facts if f.get('country') == country]
        lines.append(f"  {country}: {count} — {', '.join(names)}")
    lines += ["", "Fans by occupation category:"]
    for cat, count in category_counts.most_common():
        lines.append(f"  {cat}: {count}")
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

        # 5. Call Claude.
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            system = _build_system_prompt(_load_facts())
            msg = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
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
