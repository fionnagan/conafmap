// ── Ask the Map ───────────────────────────────────────────────────────────────
(function () {
  const form      = document.getElementById('askForm');
  const input     = document.getElementById('askInput');
  const btn       = document.getElementById('askBtn');
  const answerEl  = document.getElementById('askAnswer');
  const wrapEl    = document.getElementById('askAnswerWrap');
  const shareBtn  = document.getElementById('askShareBtn');
  const chips     = document.getElementById('askSuggestions');
  if (!form || !input || !answerEl) return;

  let busy = false;
  let lastQuestion = '';
  let lastAnswerText = '';

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
    wrapEl.hidden = false;
    answerEl.className = 'ask-answer' + (kind ? ' ask-answer--' + kind : '');
    if (kind === 'error' || kind === 'loading') {
      answerEl.textContent = text;
    } else {
      answerEl.innerHTML = mdToHtml(text);
    }
    shareBtn.hidden = kind === 'loading' || kind === 'error';
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
        lastQuestion = question;
        lastAnswerText = data.answer;
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

  const copyBtn = document.getElementById('askCopyBtn');

  function shareText() {
    return '"' + lastQuestion + '"\n\n' + lastAnswerText + '\n\nMore at conafmap.vercel.app';
  }

  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      navigator.clipboard.writeText(shareText()).then(function () {
        const orig = copyBtn.innerHTML;
        copyBtn.textContent = 'Copied!';
        setTimeout(function () { copyBtn.innerHTML = orig; }, 2000);
      }).catch(() => {});
    });
  }

  if (shareBtn) {
    shareBtn.addEventListener('click', function () {
      if (navigator.share) {
        navigator.share({
          title: 'Conan Fan Map',
          text: shareText()
        }).catch(() => {});
      } else {
        navigator.clipboard.writeText(shareText()).then(function () {
          const orig = shareBtn.innerHTML;
          shareBtn.textContent = 'Copied!';
          setTimeout(function () { shareBtn.innerHTML = orig; }, 2000);
        }).catch(() => {});
      }
    });
  }

  // ── Rotating prompts ────────────────────────────────────────────────────────
  // Sample-question chips and the input placeholder both cycle through a pool on
  // a timer so the section feels alive. Chips pause while hovered (don't move a
  // click target out from under the cursor) or while a request is in flight; the
  // placeholder only rotates while the input is empty and unfocused.
  const QUESTION_POOL = [
    "Who's the fan from Norway?",
    "How many fans are from Canada?",
    "What does the fan from Christchurch do?",
    "Which country has the most fans?",
    "Who's the most recent fan?",
    "Are there any fans from Antarctica?",
    "How many countries are represented?",
    "Which fans appeared on Conan Must Go?",
    "What's the most common job among the fans?",
    "Are there any fans from Ireland?",
    "Who's the fan from Iceland?",
    "How many fans are teachers?",
    "What do Conan's fans do for a living?",
    "Which continent has the fewest fans?"
  ];
  const PLACEHOLDER_POOL = [
    "What are you curious about Conan's fans?",
    "Curious which country has the most fans?",
    "Wondering who the newest fan is?",
    "Ask about a fan from your country…",
    "Curious what Conan's fans do for a living?",
    "Want to know who's furthest from home?",
    "Curious if there's a fan from Antarctica?",
    "Ask how many fans are from Canada…"
  ];

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function chipsHtml() {
    return shuffle(QUESTION_POOL).slice(0, 3)
      .map(function (q) { return '<button type="button" class="ask-chip">' + q + '</button>'; })
      .join('');
  }

  function pickPlaceholder() {
    let p;
    do { p = PLACEHOLDER_POOL[Math.floor(Math.random() * PLACEHOLDER_POOL.length)]; }
    while (p === input.placeholder && PLACEHOLDER_POOL.length > 1);
    return p;
  }

  if (chips) {
    // First paint: random set, no fade.
    chips.innerHTML = chipsHtml();
    let suggestionsHovered = false;
    chips.addEventListener('mouseenter', function () { suggestionsHovered = true; });
    chips.addEventListener('mouseleave', function () { suggestionsHovered = false; });
    setInterval(function () {
      if (suggestionsHovered || busy) return;
      chips.style.opacity = '0';
      setTimeout(function () { chips.innerHTML = chipsHtml(); chips.style.opacity = '1'; }, 180);
    }, 9000);
  }

  input.placeholder = pickPlaceholder();
  setInterval(function () {
    if (document.activeElement !== input && !input.value) input.placeholder = pickPlaceholder();
  }, 4500);
})();
