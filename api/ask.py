"""
api/ask.py — Fan-facing Q&A endpoint for the Conan Fan Map.

POST /api/ask  {"question": "who's the fan from Norway?"}
  → {"answer": "..."}

Reads api/fans_context.json (188 fan facts, emitted by build.py), passes them as
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

CONTEXT_FILE     = Path(__file__).parent / 'fans_context.json'
MAX_BODY_BYTES   = 2000
MAX_QUESTION_LEN = 500
MAX_TOKENS       = 400
MODEL            = 'claude-haiku-4-5'

SYSTEM_TEMPLATE = """You are the Q&A assistant for the Conan Fan Map — an interactive map of fans \
who appeared on "Conan O'Brien Needs a Fan" (podcast) and "Conan Must Go" (HBO show).

Answer ONLY using the fan data below. Each line is one fan:
date | name | location | occupation | episode | topic | Must Go season (or "-")

{table}

Rules:
- Answer questions about these fans only. If asked anything off-topic (general knowledge, \
coding, opinions, anything not answerable from the data), politely decline and steer back to the fans.
- Be concise and friendly. This shows on a fan website.
- If the data doesn't contain the answer, say so plainly. Do not invent fans or details.
- When counting or listing, scan the full dataset carefully BEFORE writing your answer, \
then state the result directly. Never show recounting, second-guessing, or corrections \
mid-response ("wait", "actually", "let me recount", etc.). Give one confident answer.
- For counts: state the number, then list the names/locations. Do not revise the count after stating it."""


def _load_facts():
    with open(CONTEXT_FILE, encoding='utf-8') as f:
        return json.load(f)


def _build_system_prompt(facts):
    lines = []
    for f in facts:
        season = f"S{f['season']}" if f.get('mustGo') and f.get('season') else '-'
        lines.append(
            f"{f['date']} | {f['name']} | {f['location']} | {f['occupation']} | "
            f"{f['episode']} | {f['topic']} | {season}"
        )
    return SYSTEM_TEMPLATE.format(table='\n'.join(lines))


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Same-origin guard — browser must send Origin/Referer matching our Host.
        if not self._is_same_origin():
            return self._send(403, {'error': 'forbidden'})

        # 2. Body size cap.
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._send(413, {'error': 'request too large'})

        # 3. Parse JSON body.
        try:
            payload = json.loads(self.rfile.read(length))
            question = str(payload.get('question', '')).strip()
        except Exception:
            return self._send(400, {'error': 'invalid JSON'})

        if not question:
            return self._send(400, {'error': 'empty question'})
        question = question[:MAX_QUESTION_LEN]

        # 4. Key must be configured. Accept either name — ANTHROPIC_API_KEY (the
        #    SDK default) or CLAUDE (the name this project uses for the Actions secret),
        #    so it works regardless of which the Vercel env var was given.
        api_key = (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('CLAUDE')
                   or os.environ.get('Anthropic_API', ''))
        if not api_key:
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
            return self._send(200, {'answer': answer})
        except Exception:
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
