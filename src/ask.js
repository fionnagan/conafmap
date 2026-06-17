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

  function show(text, kind) {
    answer.hidden = false;
    answer.className = 'ask-answer' + (kind ? ' ask-answer--' + kind : '');
    answer.textContent = text;
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
