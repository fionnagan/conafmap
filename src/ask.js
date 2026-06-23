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

  const citeEl = document.getElementById('askCitations');

  // Resolve a citation back to a fan in the FANS dataset (for a clickable pin).
  function resolveFan(c) {
    if (typeof FANS === 'undefined') return null;
    const ep = (c.episode_title || '').toLowerCase();
    const nm = (c.fan_name || '').toLowerCase();
    return FANS.find(function (f) {
      return (f.episode || '').toLowerCase() === ep &&
             (nm === '' || (f.name || '').toLowerCase() === nm ||
              (f.fullName || '').toLowerCase() === nm);
    }) || FANS.find(function (f) { return (f.episode || '').toLowerCase() === ep; }) || null;
  }

  function esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;');
  }

  function renderCitations(citations) {
    if (!citeEl) return;
    if (!citations || !citations.length) { citeEl.hidden = true; citeEl.innerHTML = ''; return; }
    const items = citations.slice(0, 6).map(function (c) {
      const fan = resolveFan(c);
      const ts = c.timestamp ? '<span class="ask-cite-ts">' + esc(c.timestamp) + '</span>' : '';
      const label = esc(c.fan_name || (fan && fan.name) || 'Fan') +
                    ' · <em>' + esc(c.episode_title) + '</em> ' + ts;
      const snippet = c.snippet ? '<span class="ask-cite-snip">“' + esc(c.snippet) + '”</span>' : '';
      if (fan && fan.slug) {
        return '<li><a href="#map" class="ask-cite" data-slug="' + esc(fan.slug) + '">' +
               label + '</a>' + snippet + '</li>';
      }
      return '<li><span class="ask-cite ask-cite--static">' + label + '</span>' + snippet + '</li>';
    }).join('');
    citeEl.innerHTML = '<div class="ask-cite-head">Sources</div><ul>' + items + '</ul>';
    citeEl.hidden = false;
  }

  function show(text, kind, citations) {
    wrapEl.hidden = false;
    answerEl.className = 'ask-answer' + (kind ? ' ask-answer--' + kind : '');
    if (kind === 'error' || kind === 'loading') {
      answerEl.textContent = text;
    } else {
      answerEl.innerHTML = mdToHtml(text);
    }
    renderCitations(kind ? null : citations);
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
        show(data.answer, null, Array.isArray(data.citations) ? data.citations : []);
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

  // Clicking a source flies the map to that fan's pin and opens their popup.
  if (citeEl) {
    citeEl.addEventListener('click', function (e) {
      const a = e.target.closest('.ask-cite[data-slug]');
      if (!a) return;
      const slug = a.getAttribute('data-slug');
      if (typeof flyToFan === 'function' && slug) {
        e.preventDefault();
        flyToFan(slug);
        const map = document.getElementById('map');
        if (map) map.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
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
  // These fire real questions when clicked, so every one is chosen to return a
  // strong, cited answer — a mix of transcript content, host synthesis, and
  // delightfully specific moments that show off what you can actually ask.
  const QUESTION_POOL = [
    "What's the most unusual job a fan has had?",
    "Where is Conan's wife from?",
    "What career advice has Conan given fans?",
    "Which fan brought a tiny airplane into a wrestling ring?",
    "What does Conan say about being a dad?",
    "Which fan asked Conan to help them get engaged?",
    "What recurring bits does Matt do?",
    "What does Sona actually do on the podcast?",
    "Who's the fan that picks locks for a living?",
    "Which fan is a professional luchador?",
    "What life advice comes up again and again?",
    "Which fan studied reptiles?",
    "How many countries have a Conan fan?",
    "Who's the museum paleontologist?"
  ];
  const PLACEHOLDER_POOL = [
    "Ask about a fan's story — or something Conan said…",
    "Curious what advice Conan gives fans?",
    "Wondering what the weirdest fan job is?",
    "Ask what Conan thinks about being a dad…",
    "Try: what does Sona do on the show?",
    "Ask about a recurring Matt bit…",
    "Curious where Conan's wife is from?",
    "Ask about any fan — their job, their question, their moment…",
    "What life lessons keep coming up on the show?"
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
