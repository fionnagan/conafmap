// ============================================================
// FAN OF THE WEEK SPOTLIGHT
// ============================================================
(function initSpotlight() {
  // Eligible: Must Go fans + fans with real Q&A or highlights
  const eligible = FANS.filter(f =>
    f.mustGo ||
    f.fanQuestion ||
    f.conanResponse ||
    (f.highlights && f.highlights.length > 0)
  );
  if (!eligible.length) return;

  const section = document.getElementById('spotlightSection');
  if (!section) return;

  // Weekly rotation — same fan all 7 days, changes each Monday midnight
  const weekSeed = Math.floor(Date.now() / (7 * 24 * 60 * 60 * 1000));
  const fan = eligible[weekSeed % eligible.length];

  const dateStr = new Date(fan.date + 'T12:00:00').toLocaleDateString('en-US',
    { month: 'long', day: 'numeric', year: 'numeric' });

  const badge = fan.mustGo
    ? `<span class="spotlight-badge mustgo">\uD83C\uDFAC Must Go${fan.mustGoSeason ? ' \u2014 Season ' + fan.mustGoSeason : ''}</span>`
    : `<span class="spotlight-badge fan">\uD83C\uDF99 Needs a Fan</span>`;

  const qHtml = fan.fanQuestion
    ? `<div class="spotlight-qa">
         <div class="spotlight-qa-label">Fan</div>
         <div class="spotlight-qa-text">\u201c${fan.fanQuestion}\u201d</div>
       </div>`
    : '';

  const rHtml = fan.conanResponse
    ? `<div class="spotlight-qa spotlight-qa-conan">
         <div class="spotlight-qa-label">Conan</div>
         <div class="spotlight-qa-text">\u201c${fan.conanResponse}\u201d</div>
       </div>`
    : '';

  const hlHtml = fan.highlights && fan.highlights.length
    ? `<ul class="spotlight-highlights">${fan.highlights.map(h => `<li>${h}</li>`).join('')}</ul>`
    : '';

  const playerHtml = fan.simplecastId
    ? `<div class="spotlight-player">
         <iframe height="52" src="https://player.simplecast.com/${fan.simplecastId}?dark=true"
           allow="autoplay" style="width:100%;border:0;border-radius:8px;"></iframe>
       </div>`
    : '';

  section.innerHTML = `
    <div class="spotlight-inner">
      <div class="spotlight-header-row">
        <div class="spotlight-eyebrow">\u2B50 Fan of the Week</div>
      </div>
      <div class="spotlight-layout">
        <div class="spotlight-left">
          <div class="spotlight-name-row">
            <div class="spotlight-name">${fan.fullName || fan.name}</div>
            ${badge}
          </div>
          <div class="spotlight-meta">${fan.displayLocation || fan.location} \u00B7 ${fan.occupation}</div>
          <div class="spotlight-ep">${fan.episode} \u00B7 ${dateStr}</div>
          ${qHtml}${rHtml}${hlHtml}
        </div>
        <div class="spotlight-right">
          ${playerHtml}
          <button class="spotlight-share-btn" onclick="sharePin('${fan.slug}', event)">\uD83D\uDD17 Share this fan</button>
        </div>
      </div>
    </div>`;

  section.style.display = 'block';
})();
