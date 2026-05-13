// ============================================================
// FAN OF THE DAY SPOTLIGHT
// ============================================================
(function initSpotlight() {
  // Eligible: Must Go fans + fans with real Q&A, highlights, or summary
  const eligible = FANS.filter(f =>
    f.mustGo ||
    f.fanQuestion ||
    f.conanResponse ||
    (f.highlights && f.highlights.length > 0) ||
    (f.fanQuestions && f.fanQuestions.length > 0) ||
    f.summary
  );
  if (!eligible.length) return;

  const section = document.getElementById('spotlightSection');
  if (!section) return;

  // Daily rotation — changes each day at midnight
  const daySeed = Math.floor(Date.now() / (24 * 60 * 60 * 1000));
  const fan = eligible[daySeed % eligible.length];

  const dateStr = new Date(fan.date + 'T12:00:00').toLocaleDateString('en-US',
    { month: 'long', day: 'numeric', year: 'numeric' });

  const badge = fan.mustGo
    ? `<span class="spotlight-badge mustgo">🎬 Must Go${fan.mustGoSeason ? ', Season ' + fan.mustGoSeason : ''}</span>`
    : `<span class="spotlight-badge fan">🎙 Needs a Fan</span>`;

  // ── Summary — max 2 sentences, hard-capped at 260 chars ─────────────────
  const _s2 = typeof _firstSentences === 'function' ? _firstSentences(fan.summary, 2, 260) : '';
  const summaryHtml = _s2
    ? `<div class="spotlight-summary">${_s2}</div>`
    : '';

  // ── Q&A — prefer structured fanQuestions array ──────────────────────────
  let qHtml = '';
  let rHtml = '';
  if (fan.fanQuestions && fan.fanQuestions.length > 0) {
    qHtml = fan.fanQuestions.map(q => {
      const cr = q.conan_response || {};
      const crText = typeof _conanToFirstPerson === 'function'
        ? _conanToFirstPerson(cr.quote || cr.summary || '')
        : (cr.quote || cr.summary || '');
      return `<div class="spotlight-qa">
        <div class="spotlight-qa-label">Fan</div>
        <div class="spotlight-qa-text">"${q.question}"</div>
      </div>` + (crText
        ? `<div class="spotlight-qa spotlight-qa-conan">
             <div class="spotlight-qa-label">Conan</div>
             <div class="spotlight-qa-text">"${crText}"</div>
           </div>`
        : '');
    }).join('');
  } else {
    qHtml = fan.fanQuestion
      ? `<div class="spotlight-qa">
           <div class="spotlight-qa-label">Fan</div>
           <div class="spotlight-qa-text">"${fan.fanQuestion}"</div>
         </div>`
      : '';
    const crSpotlight = typeof _conanToFirstPerson === 'function'
      ? _conanToFirstPerson(fan.conanResponse || '')
      : (fan.conanResponse || '');
    rHtml = crSpotlight
      ? `<div class="spotlight-qa spotlight-qa-conan">
           <div class="spotlight-qa-label">Conan</div>
           <div class="spotlight-qa-text">"${crSpotlight}"</div>
         </div>`
      : '';
  }

  // ── Highlights — narrative bullets, no category labels or bold titles ────
  const _SPOTLIGHT_CAT_COLOR = {
    comedy:'#F26522',advice:'#3498db',emotional:'#e74c3c',awkward:'#9b59b6',
    absurd:'#c94e12',storytelling:'#2ecc71',career:'#f39c12',
    relationship:'#e91e63',callback:'#1abc9c'
  };
  let hlHtml = '';
  if (fan.highlightsV2 && fan.highlightsV2.length > 0) {
    const _strip  = typeof _stripDash       === 'function' ? _stripDash       : s => s;
    const _first1 = typeof _firstSentences  === 'function' ? _firstSentences  : (s) => s;
    const items = fan.highlightsV2.map(h => {
      const c      = _SPOTLIGHT_CAT_COLOR[h.category] || '#F26522';
      const bullet = _first1(h.summary, 1, 140);
      return bullet ? `<li style="border-left-color:${c}90">${bullet}</li>` : '';
    }).filter(Boolean).join('');
    if (items) hlHtml = `<ul class="spotlight-highlights">${items}</ul>`;
  } else if (fan.highlights && fan.highlights.length) {
    const _strip = typeof _stripDash === 'function' ? _stripDash : s => s;
    hlHtml = `<ul class="spotlight-highlights">${fan.highlights.map(h => `<li>${_strip(h)}</li>`).join('')}</ul>`;
  }

  const playerHtml = fan.simplecastId
    ? `<div class="spotlight-player">
         <iframe height="52" src="https://player.simplecast.com/${fan.simplecastId}?dark=true"
           allow="autoplay" style="width:100%;border:0;border-radius:8px;"></iframe>
       </div>`
    : '';

  section.innerHTML = `
    <div class="spotlight-inner">
      <div class="spotlight-header-row">
        <div class="spotlight-eyebrow">🥥 Fan of the Day</div>
      </div>
      <div class="spotlight-layout">
        <div class="spotlight-left">
          <div class="spotlight-name-row">
            <div class="spotlight-name">${fan.fullName || fan.name}</div>
            ${badge}
          </div>
          <div class="spotlight-meta">${fan.displayLocation || fan.location} · ${fan.occupation}</div>
          <div class="spotlight-ep">${fan.episode} · ${dateStr}</div>
          ${summaryHtml}
          ${qHtml}${rHtml}${hlHtml}
        </div>
        <div class="spotlight-right">
          ${playerHtml}
          <button class="spotlight-share-btn" onclick="sharePin('${fan.slug}', event)">🔗 Share this fan</button>
        </div>
      </div>
    </div>`;

  section.style.display = 'block';
})();
