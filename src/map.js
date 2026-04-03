// ============================================================
// MAP INIT
// ============================================================
const ORANGE   = '#F26522';
const MUSTGO_C = '#0057B8';

const map = L.map('map', {
  zoomControl:          true,
  scrollWheelZoom:      false,   // disabled by default; Ctrl+scroll re-enables
  worldCopyJump:        false,
  maxBounds:            [[-90, -180], [90, 180]],
  maxBoundsViscosity:   1.0,
  minZoom:              2
}).setView([20, 10], 2);

// ── Scroll guard (Ctrl/Cmd+scroll to zoom, otherwise pass through) ────────────
(function () {
  const mapEl = document.getElementById('map');
  let hintTimer = null;

  function showHint() {
    let hint = document.getElementById('map-scroll-hint');
    if (!hint) {
      hint = document.createElement('div');
      hint.id = 'map-scroll-hint';
      hint.textContent = navigator.platform.includes('Mac')
        ? '⌘ + scroll to zoom'
        : 'Ctrl + scroll to zoom';
      mapEl.parentNode.appendChild(hint);
    }
    hint.classList.add('visible');
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => hint.classList.remove('visible'), 1800);
  }

  mapEl.addEventListener('wheel', function (e) {
    if (e.ctrlKey || e.metaKey) {
      map.scrollWheelZoom.enable();
    } else {
      map.scrollWheelZoom.disable();
      showHint();
    }
  }, { passive: true });

  // Touch: two-finger pinch passes through naturally; single-finger scrolls page
  mapEl.addEventListener('touchstart', function (e) {
    if (e.touches.length >= 2) {
      map.dragging.disable();
    }
  }, { passive: true });
  mapEl.addEventListener('touchend', function () {
    map.dragging.enable();
  }, { passive: true });
})();

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

// ── Popup HTML builder ────────────────────────────────────────────────────────
function buildPopupHTML(f) {
  const badgeLabel = f.mustGo
    ? `\uD83C\uDFAC Must Go${f.mustGoSeason ? ' \u2014 Season ' + f.mustGoSeason : ''}`
    : '\uD83C\uDF99 Needs a Fan';
  const badge = f.mustGo
    ? `<span class="popup-badge mustgo">${badgeLabel}</span>`
    : `<span class="popup-badge fan">${badgeLabel}</span>`;

  const dateStr = new Date(f.date + 'T12:00:00').toLocaleDateString('en-US',
    { month: 'short', day: 'numeric', year: 'numeric' });

  const question = f.fanQuestion
    ? `<div class="popup-section"><h4>\u2753 Fan</h4>
       <div class="popup-question">\u201c${f.fanQuestion}\u201d</div></div>`
    : '';

  const response = f.conanResponse
    ? `<div class="popup-section">
       <h4 class="popup-response-label">\uD83C\uDF99 Conan</h4>
       <div class="popup-question" style="border-left-color:var(--mustgo);">\u201c${f.conanResponse}\u201d</div></div>`
    : '';

  const hl = (f.highlights || []).map(h => `<li>${h}</li>`).join('');
  const highlightsHtml = hl
    ? `<div class="popup-section"><h4>\u2B50 Highlights</h4>
       <ul class="popup-highlights">${hl}</ul></div>`
    : '';

  const player = f.simplecastId
    ? `<div class="popup-player">
       <iframe height="52"
         src="https://player.simplecast.com/${f.simplecastId}?dark=true"
         allow="autoplay"></iframe></div>`
    : '';

  const epLink = f.teamcocoUrl
    ? `<div style="margin-top:6px;font-size:11px;">
       <a href="${f.teamcocoUrl}" target="_blank"
          style="color:var(--orange);text-decoration:none;">\u25B6 Listen on Team Coco</a></div>`
    : '';

  const shareBtn = `<button class="popup-share-btn" onclick="sharePin('${f.slug}', event)" title="Share this fan">\uD83D\uDD17 Share this fan</button>`;

  return `<div class="popup-inner">
    <div class="popup-top-row">
      ${badge}
      ${shareBtn}
    </div>
    <div class="popup-name">${f.fullName || f.name}</div>
    <div class="popup-ep">${f.episode} \u00B7 ${dateStr}</div>
    <div class="popup-grid">
      <div class="popup-field"><label>\uD83D\uDCCD Location</label><p>${f.displayLocation || f.location}</p></div>
      <div class="popup-field"><label>\uD83D\uDCBC Occupation</label><p>${f.occupation}</p></div>
    </div>
    ${question}
    ${response}
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

FANS.filter(f => f.coords).forEach(f => {
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
