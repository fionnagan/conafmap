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
    ? `<span class="spotlight-badge mustgo">🎬 Must Go${fan.mustGoSeason ? ' — Season ' + fan.mustGoSeason : ''}</span>`
    : `<span class="spotlight-badge fan">🎙 Needs a Fan</span>`;

  // ── Summary ─────────────────────────────────────────────────────────────
  const summaryHtml = (fan.summary && fan.summary.length > 50)
    ? `<div class="spotlight-summary">${fan.summary.slice(0, 360)}${fan.summary.length > 360 ? '…' : ''}</div>`
    : '';

  // ── Q&A — prefer structured fanQuestions array ──────────────────────────
  let qHtml = '';
  let rHtml = '';
  if (fan.fanQuestions && fan.fanQuestions.length > 0) {
    qHtml = fan.fanQuestions.map(q => {
      const cr = q.conan_response || {};
      const crText = cr.quote || cr.summary || '';
      return `<div class="spotlight-qa">
        <div class="spotlight-qa-label">Fan</div>
        <div class="spotlight-qa-text">“${q.question}”</div>
      </div>` + (crText
        ? `<div class="spotlight-qa spotlight-qa-conan">
             <div class="spotlight-qa-label">Conan</div>
             <div class="spotlight-qa-text">“${crText}”</div>
           </div>`
        : '');
    }).join('');
  } else {
    qHtml = fan.fanQuestion
      ? `<div class="spotlight-qa">
           <div class="spotlight-qa-label">Fan</div>
           <div class="spotlight-qa-text">“${fan.fanQuestion}”</div>
         </div>`
      : '';
    rHtml = fan.conanResponse
      ? `<div class="spotlight-qa spotlight-qa-conan">
           <div class="spotlight-qa-label">Conan</div>
           <div class="spotlight-qa-text">“${fan.conanResponse}”</div>
         </div>`
      : '';
  }

  // ── Highlights — prefer highlightsV2 ────────────────────────────────────
  let hlHtml = '';
  if (fan.highlightsV2 && fan.highlightsV2.length > 0) {
    hlHtml = `<ul class="spotlight-highlights">${fan.highlightsV2.map(h =>
      `<li><span class="spotlight-hl-cat">${h.category || ''}</span><strong>${h.title}</strong> — ${h.summary}</li>`
    ).join('')}</ul>`;
  } else if (fan.highlights && fan.highlights.length) {
    hlHtml = `<ul class="spotlight-highlights">${fan.highlights.map(h => `<li>${h}</li>`).join('')}</ul>`;
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
