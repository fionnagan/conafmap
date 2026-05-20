// ============================================================
// MAP INIT
// ============================================================
const ORANGE   = '#F26522';
const MUSTGO_C = '#0057B8';

const map = L.map('map', {
  zoomControl:          true,
  scrollWheelZoom:      true,
  worldCopyJump:        false,
  maxBounds:            [[-90, -180], [90, 180]],
  maxBoundsViscosity:   1.0,
  minZoom:              2
}).setView([20, 10], 2);


L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap, &copy; CARTO',
  maxZoom: 19,
  noWrap: true
}).addTo(map);

// ── Icons ────────────────────────────────────────────────────────────────────
function makeIcon(mustGo) {
  const c = mustGo ? MUSTGO_C : ORANGE;
  return L.divIcon({
    className: '',
    iconAnchor: [14, 36],
    popupAnchor: [0, -36],
    html: `<svg width="28" height="38" viewBox="0 0 28 38" xmlns="http://www.w3.org/2000/svg">
      <path d="M14 0C6.27 0 0 6.27 0 14c0 9.63 14 24 14 24S28 23.63 28 14C28 6.27 21.73 0 14 0z"
            fill="${c}" stroke="rgba(0,0,0,0.4)" stroke-width="1.5"/>
      <circle cx="14" cy="14" r="6" fill="rgba(255,255,255,0.9)"/>
    </svg>`
  });
}

// ── Text helpers (shared with spotlight.js) ──────────────────────────────────
function _stripDash(s) {
  return (s || '')
    .replace(/,?\s*—\s*/g, ', ')
    .replace(/,\s*,/g, ',')
    .trim();
}

function _conanToFirstPerson(s) {
  if (!s) return '';
  let r = s
    .replace(/^Conan said he /i,  'I ')
    .replace(/^Conan said /i,     'I said ')
    .replace(/^Conan /i,          'I ')
    .replace(/ he /g,    ' I ')
    .replace(/ his /g,   ' my ')
    .replace(/ him /g,   ' me ')
    .replace(/\bhimself\b/g, 'myself')
    .replace(/\bI I\b/g,     'I')
    .trim();
  return r.charAt(0).toUpperCase() + r.slice(1);
}

function _isValidCoord(lat, lng) {
  return (
    typeof lat === 'number' && typeof lng === 'number' &&
    isFinite(lat) && isFinite(lng) &&
    lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180
  );
}

// ── Popup HTML builder ────────────────────────────────────────────────────────
function buildPopupHTML(f) {
  const badgeLabel = f.mustGo
    ? `🎬 Must Go${f.mustGoSeason ? ', Season ' + f.mustGoSeason : ''}`
    : '🎙 Needs a Fan';
  const badge = f.mustGo
    ? `<span class="popup-badge mustgo">${badgeLabel}</span>`
    : `<span class="popup-badge fan">${badgeLabel}</span>`;

  const dateStr = new Date(f.date + 'T12:00:00').toLocaleDateString('en-US',
    { month: 'short', day: 'numeric', year: 'numeric' });

  const summaryText = _stripDash(f.summary);
  const summaryHtml = summaryText
    ? `<div class="popup-section-label">📍 Episode Summary</div>
       <div class="popup-summary-section">
         <div class="popup-summary-text">${summaryText}</div>
       </div>`
    : '';

  let qaHtml = '';
  const _makeQaItem = (text, isFan) => {
    const cls = isFan ? 'popup-qa-fan' : 'popup-qa-conan';
    return `<div class="popup-qa-item ${cls}"><p>"${text}"</p></div>`;
  };
  if (f.fanQuestions && f.fanQuestions.length > 0) {
    const pairs = f.fanQuestions.map(q => {
      const cr     = q.conan_response || {};
      const crText = _conanToFirstPerson(cr.quote || cr.summary || '');
      return `<div class="popup-section-label">❓ Fan</div>${_makeQaItem(q.question, true)}`
        + (crText ? `<div class="popup-section-label">🎙 Conan</div>${_makeQaItem(crText, false)}` : '');
    }).join('');
    if (pairs) qaHtml = `<div class="popup-qa">${pairs}</div>`;
  } else {
    let parts = '';
    if (f.fanQuestion) parts += `<div class="popup-section-label">❓ Fan</div>${_makeQaItem(f.fanQuestion, true)}`;
    const crText = _conanToFirstPerson(f.conanResponse || '');
    if (crText) parts += `<div class="popup-section-label">🎙 Conan</div>${_makeQaItem(crText, false)}`;
    if (parts) qaHtml = `<div class="popup-qa">${parts}</div>`;
  }

  let highlightsHtml = '';
  const _hlItems = (f.highlightsV2 && f.highlightsV2.length > 0)
    ? f.highlightsV2.map(h => _stripDash(h.summary || h.title)).filter(Boolean)
    : (f.highlights || []).map(h => _stripDash(h)).filter(Boolean);
  if (_hlItems.length) {
    const lis = _hlItems.map(t => `<li>${t}</li>`).join('');
    highlightsHtml = `<div class="popup-section-label">⭐ Highlights</div>
      <ul class="popup-hl-list">${lis}</ul>`;
  }

  const player = f.simplecastId
    ? `<div class="popup-player">
       <iframe height="52"
         src="https://player.simplecast.com/${f.simplecastId}?dark=true"
         allow="autoplay"></iframe></div>`
    : '';

  const epLink = f.teamcocoUrl
    ? `<div style="margin-top:6px;font-size:11px;">
       <a href="${f.teamcocoUrl}" target="_blank"
          style="color:var(--orange);text-decoration:none;">▶ Listen on Team Coco</a></div>`
    : '';

  const shareBtn = `<button class="popup-share-btn" onclick="sharePin('${f.slug}', event)" title="Share this fan">🔗 Share this fan</button>`;

  return `<div class="popup-inner">
    <div class="popup-top-row">
      <div class="popup-name-group">
        <div class="popup-name">${f.fullName || f.name}</div>
        ${badge}
      </div>
      ${shareBtn}
    </div>
    <div class="popup-ep">${f.episode} · ${dateStr}</div>
    <div class="popup-grid">
      <div class="popup-field"><label>📍 Location</label><p>${f.displayLocation || f.location}</p></div>
      <div class="popup-field"><label>💼 Occupation</label><p>${f.occupation}</p></div>
    </div>
    ${summaryHtml}
    ${qaHtml}
    ${highlightsHtml}
    ${player}
    ${epLink}
  </div>`;
}

// ── Share pin ─────────────────────────────────────────────────────────────────
function sharePin(slug, evt) {
  if (evt) evt.stopPropagation();
  const url = window.location.origin + window.location.pathname + '?fan=' + encodeURIComponent(slug);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(showShareToast);
  } else {
    const ta = document.createElement('textarea');
    ta.value = url;
    ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    try { document.execCommand('copy'); showShareToast(); } catch(e) {}
    document.body.removeChild(ta);
  }
}

function showShareToast() {
  const t = document.getElementById('shareToast');
  if (!t) return;
  t.classList.add('visible');
  setTimeout(() => t.classList.remove('visible'), 2200);
}

// ── Mobile detection ──────────────────────────────────────────────────────────
function isMobile() { return window.innerWidth < 768; }

// ── Bottom sheet ──────────────────────────────────────────────────────────────
function openBottomSheet(f) {
  const sheet   = document.getElementById('bottomSheet');
  const overlay = document.getElementById('sheetOverlay');
  const body    = document.getElementById('sheetBody');
  if (!sheet || !body) return;
  body.innerHTML = buildPopupHTML(f);
  sheet.classList.add('open');
  if (overlay) overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeBottomSheet() {
  const sheet   = document.getElementById('bottomSheet');
  const overlay = document.getElementById('sheetOverlay');
  if (!sheet) return;
  sheet.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
  document.body.style.overflow = '';
}

// ── URL sync ──────────────────────────────────────────────────────────────────
function syncUrl(slug) {
  const url = slug
    ? window.location.pathname + '?fan=' + encodeURIComponent(slug)
    : window.location.pathname;
  history.replaceState({ fan: slug }, '', url);
}

function clearUrl() {
  history.replaceState({}, '', window.location.pathname);
}

// ── Marker cluster + render ───────────────────────────────────────────────────
const clusters = L.markerClusterGroup({ maxClusterRadius: 50, spiderfyOnMaxZoom: true });
const markerMap = {};  // slug → Leaflet marker

const _validFans = FANS.filter(function(f) {
  return f.coords && f.coords.length >= 2 && _isValidCoord(f.coords[0], f.coords[1]);
});
_validFans.forEach(f => {
  const m = L.marker(f.coords, { icon: makeIcon(f.mustGo) });

  // Desktop: standard popup
  m.bindPopup(buildPopupHTML(f), {
    maxWidth: 560,
    minWidth: 440,
    keepInView: true,
    autoPanPaddingTopLeft:     L.point(20, 130),
    autoPanPaddingBottomRight: L.point(20, 40)
  });

  m.on('click', function() {
    if (navigator.vibrate) navigator.vibrate([10]);
    syncUrl(f.slug);
    if (isMobile()) {
      // prevent Leaflet auto-popup on mobile, use bottom sheet instead
      m.closePopup();
      openBottomSheet(f);
    }
    // desktop: Leaflet handles popup automatically via bindPopup
  });

  clusters.addLayer(m);
  if (f.slug) markerMap[f.slug] = m;
});

map.addLayer(clusters);

// Fit map to all fan pins on first load
if (_validFans.length > 0) {
  const bounds = L.latLngBounds(_validFans.map(function(f) { return f.coords; }));
  map.fitBounds(bounds, { padding: [50, 50], maxZoom: 4, animate: false });
}

// Clear URL when desktop popup closes
map.on('popupclose', function() {
  clearUrl();
});

// ── Legend toggle ─────────────────────────────────────────────────────────────
function toggleLegend() {
  const legend = document.getElementById('mapLegend');
  if (legend) legend.classList.toggle('collapsed');
}

// Collapse legend by default on mobile
(function initLegend() {
  if (window.innerWidth < 640) {
    const legend = document.getElementById('mapLegend');
    if (legend) legend.classList.add('collapsed');
  }
})();


// ── Fullscreen control — CSS-only container-scoped ───────────────────────────
let _mapFsActive = false;

function toggleFullscreen() {
  const container = document.getElementById('map').parentElement;
  const btn       = document.getElementById('fullscreenToggle');
  _mapFsActive = !_mapFsActive;
  if (_mapFsActive) {
    container.classList.add('map-fullscreen');
    if (btn) { btn.innerHTML = '✕'; btn.setAttribute('aria-label', 'Exit fullscreen'); }
  } else {
    container.classList.remove('map-fullscreen');
    if (btn) { btn.innerHTML = '⛶'; btn.setAttribute('aria-label', 'Enter fullscreen'); }
  }
  setTimeout(function() { map.invalidateSize(); }, 200);
}

window.addEventListener('resize', function() {
  if (_mapFsActive) setTimeout(function() { map.invalidateSize(); }, 120);
});

// Bottom sheet overlay + close button
document.addEventListener('DOMContentLoaded', function() {
  const overlay  = document.getElementById('sheetOverlay');
  const closeBtn = document.getElementById('sheetClose');
  if (overlay)  overlay.addEventListener('click', function() { closeBottomSheet(); clearUrl(); });
  if (closeBtn) closeBtn.addEventListener('click', function() { closeBottomSheet(); clearUrl(); });

  const fanModalOverlay = document.getElementById('fanModalOverlay');
  const fanModalClose   = document.getElementById('fanModalClose');
  if (fanModalOverlay) fanModalOverlay.addEventListener('click', closeFanModal);
  if (fanModalClose)   fanModalClose.addEventListener('click', closeFanModal);
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeFanModal();
  });
});

// ── Deep-link: ?fan=slug ──────────────────────────────────────────────────────
(function handleDeepLink() {
  const params = new URLSearchParams(window.location.search);
  const slug   = params.get('fan');
  if (!slug) return;

  const target = markerMap[slug];
  if (!target) return;

  // Wait for cluster layer to be ready then zoom to marker
  setTimeout(function() {
    clusters.zoomToShowLayer(target, function() {
      if (isMobile()) {
        const fan = FANS.find(f => f.slug === slug);
        if (fan) openBottomSheet(fan);
      } else {
        target.openPopup();
      }
    });
  }, 400);
})();

// ── Show fan detail (from table click) ───────────────────────────────────────
function showFanDetail(slug) {
  const f = FANS.find(function(fan) { return fan.slug === slug; });
  if (!f) return;
  if (navigator.vibrate) navigator.vibrate([10]);
  if (isMobile()) {
    // Open bottom sheet WITHOUT scrolling to the map
    openBottomSheet(f);
  } else {
    // Show inline modal over the table
    const modal   = document.getElementById('fanModal');
    const overlay = document.getElementById('fanModalOverlay');
    const body    = document.getElementById('fanModalBody');
    if (!modal || !body) return;
    body.innerHTML = buildPopupHTML(f);
    modal.classList.add('open');
    if (overlay) overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

function closeFanModal() {
  const modal   = document.getElementById('fanModal');
  const overlay = document.getElementById('fanModalOverlay');
  if (modal)   { modal.classList.remove('open'); }
  if (overlay) { overlay.classList.remove('open'); }
  document.body.style.overflow = '';
}

// ── Choropleth layer ─────────────────────────────────────────────────────────
// ISO 3166-1 numeric → country name (only countries in our dataset)
const ISO_NAMES = {
  36:'Australia', 32:'Argentina', 56:'Belgium', 76:'Brazil', 124:'Canada',
  170:'Colombia', 191:'Croatia', 818:'Egypt', 231:'Ethiopia', 246:'Finland',
  250:'France', 276:'Germany', 300:'Greece', 348:'Hungary', 352:'Iceland',
  356:'India', 364:'Iran', 372:'Ireland', 376:'Israel', 392:'Japan',
  398:'Kazakhstan', 404:'Kenya', 417:'Kyrgyzstan', 422:'Lebanon', 484:'Mexico',
  504:'Morocco', 528:'Netherlands', 554:'New Zealand', 578:'Norway',
  608:'Philippines', 620:'Portugal', 710:'South Africa', 702:'Singapore',
  705:'Slovenia', 724:'Spain', 756:'Switzerland', 764:'Thailand',
  792:'Turkey', 804:'Ukraine', 826:'United Kingdom', 840:'United States',
};

// Build country → fan count map once
const _fanCountByCountry = {};
FANS.forEach(f => {
  if (f.country && f.country !== 'Unknown')
    _fanCountByCountry[f.country] = (_fanCountByCountry[f.country] || 0) + 1;
});

const maxFans = Math.max(...Object.values(_fanCountByCountry));

function _choroplethColor(count) {
  if (!count) return 'transparent';
  const t = Math.pow(count / maxFans, 0.5); // sqrt scale — less contrast at top
  const a = 0.10 + t * 0.60;
  return `rgba(242,101,34,${a.toFixed(2)})`;
}

let _choroplethLayer = null;
let _choroplethOn    = false;

function toggleChoropleth() {
  const btn = document.getElementById('choroplethToggle');
  if (_choroplethOn) {
    if (_choroplethLayer) map.removeLayer(_choroplethLayer);
    _choroplethOn = false;
    if (btn) { btn.classList.remove('active'); btn.textContent = '\uD83D\uDDFA\uFE0F Fan Density'; }
    return;
  }

  if (_choroplethLayer) {
    _choroplethLayer.addTo(map);
    _choroplethOn = true;
    if (btn) { btn.classList.add('active'); btn.textContent = '\u2716 Hide Density'; }
    return;
  }

  // First time — fetch TopoJSON
  if (btn) btn.textContent = 'Loading\u2026';
  fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
    .then(r => r.json())
    .then(function(topo) {
      const features = topojson.feature(topo, topo.objects.countries).features;
      _choroplethLayer = L.geoJSON(features, {
        style: function(feat) {
          const id    = parseInt(feat.id, 10);
          const name  = ISO_NAMES[id];
          const count = name ? (_fanCountByCountry[name] || 0) : 0;
          return {
            fillColor:   _choroplethColor(count),
            fillOpacity: 1,
            color:       count ? 'rgba(242,101,34,0.5)' : 'transparent',
            weight:      count ? 0.6 : 0,
          };
        },
        onEachFeature: function(feat, layer) {
          const id    = parseInt(feat.id, 10);
          const name  = ISO_NAMES[id];
          const count = name ? (_fanCountByCountry[name] || 0) : 0;
          if (count) {
            layer.bindTooltip(
              `<strong>${name}</strong><br>${count} fan${count !== 1 ? 's' : ''}`,
              { sticky: true, className: 'choropleth-tooltip' }
            );
          }
        }
      });
      _choroplethLayer.addTo(map);
      // Keep pins on top
      clusters.bringToFront();
      _choroplethOn = true;
      if (btn) { btn.classList.add('active'); btn.textContent = '\u2716 Hide Density'; }
    })
    .catch(function() {
      if (btn) btn.textContent = '\uD83D\uDDFA\uFE0F Fan Density';
    });
}

// ── Fly to fan (called from table row click) ─────────────────────────────────
function flyToFan(slug) {
  const target = markerMap[slug];
  if (!target) return;
  if (navigator.vibrate) navigator.vibrate([10]);
  // Scroll map into view first
  document.getElementById('map').scrollIntoView({ behavior: 'smooth', block: 'center' });
  setTimeout(function() {
    clusters.zoomToShowLayer(target, function() {
      syncUrl(slug);
      if (isMobile()) {
        const fan = FANS.find(function(f) { return f.slug === slug; });
        if (fan) openBottomSheet(fan);
      } else {
        target.openPopup();
      }
    });
  }, 300); // small delay to let scroll settle
}

// ── Stats bar ────────────────────────────────────────────────────────────────
(function updateStats() {
  const countries = [...new Set(FANS.map(f => f.country))].filter(c => c !== 'Unknown');
  const mustGoFans = FANS.filter(f => f.mustGo);
  document.getElementById('statFans').textContent      = FANS.length;
  document.getElementById('statCountries').textContent = countries.length;
  document.getElementById('statMustGo').textContent    = mustGoFans.length;
  document.getElementById('statWorldPct').textContent  = Math.round(countries.length / 195 * 100) + '%';
})();
