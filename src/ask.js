// ── Ask the Map ───────────────────────────────────────────────────────────────
// Posts a natural-language question to /api/ask and renders Claude's answer.
(function () {
  const form    = document.getElementById('askForm');
  const input   = document.getElementById('askInput');
  const btn     = document.getElementById('askBtn');
  const answer  = document.getElementById('askAnswer');
  const chips   = document.getElementById('askSuggestions');
  if (!form || !input || !answer) return;

  let busy = false;

  function mdToHtml(text) {
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const lines = escaped.split('\n');
    const out = [];
    let inList = false;
    for (const raw of lines) {
      const line = raw.trim();
      const bullet = line.match(/^[-*]\s+(.+)/);
      const num    = line.match(/^\d+\.\s+(.+)/);
      if (bullet || num) {
        if (!inList) { out.push(bullet ? '<ul>' : '<ol>'); inList = bullet ? 'ul' : 'ol'; }
        out.push('<li>' + applyInline(bullet ? bullet[1] : num[1]) + '</li>');
      } else {
        if (inList) { out.push('</' + inList + '>'); inList = false; }
        if (line) out.push('<p>' + applyInline(line) + '</p>');
      }
    }
    if (inList) out.push('</' + inList + '>');
    return out.join('');
  }

  function applyInline(s) {
    return s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>');
  }

  function show(text, kind) {
    answer.hidden = false;
    answer.className = 'ask-answer' + (kind ? ' ask-answer--' + kind : '');
    if (kind === 'error' || kind === 'loading') {
      answer.textContent = text;
    } else {
      answer.innerHTML = mdToHtml(text);
    }
  }

  async function ask(question) {
    question = (question || '').trim();
    if (!question || busy) return;
    busy = true;
    btn.disabled = true;
    input.disabled = true;
    show('Thinking…', 'loading');

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.answer) {
        show(data.answer, null);
      } else if (res.status === 429) {
        show('Too many questions right now — give it a moment and try again.', 'error');
      } else {
        show(data.error ? 'Sorry — ' + data.error + '.' : 'Sorry, something went wrong. Try again.', 'error');
      }
    } catch (e) {
      show('Could not reach the server. Check your connection and try again.', 'error');
    } finally {
      busy = false;
      btn.disabled = false;
      input.disabled = false;
      input.focus();
    }
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    ask(input.value);
  });

  if (chips) {
    chips.addEventListener('click', function (e) {
      const chip = e.target.closest('.ask-chip');
      if (!chip) return;
      input.value = chip.textContent;
      ask(chip.textContent);
    });
  }
})();
