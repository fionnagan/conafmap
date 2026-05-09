// ============================================================
// MAP INIT  —  MapLibre GL JS
// ============================================================
const ORANGE   = '#F26522';
const MUSTGO_C = '#0057B8';
const OCEAN    = '#11182D';   // design token: ocean / page-bg blend

// ── Helpers ─────────────────────────────────────────────────────────────────
function isMobile() { return window.innerWidth < 768; }

// ── Bottom sheet ─────────────────────────────────────────────────────────────
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

// ── Category → accent colour (used for subtle left-border only, never as text label) ──
const HL_CAT_COLOR = {
  comedy:       'var(--orange)',
  advice:       '#3498db',
  emotional:    '#e74c3c',
  awkward:      '#9b59b6',
  absurd:       '#c94e12',
  storytelling: '#2ecc71',
  career:       '#f39c12',
  relationship: '#e91e63',
  callback:     '#1abc9c'
};

// ── Popup HTML builder ────────────────────────────────────────────────────────
function buildPopupHTML(f) {
  const badgeLabel = f.mustGo
    ? `🎬 Must Go${f.mustGoSeason ? ' — Season ' + f.mustGoSeason : ''}`
    : '🎙 Needs a Fan';
  const badge = f.mustGo
    ? `<span class="popup-badge mustgo">${badgeLabel}</span>`
    : `<span class="popup-badge fan">${badgeLabel}</span>`;

  const dateStr = new Date(f.date + 'T12:00:00').toLocaleDateString('en-US',
    { month: 'short', day: 'numeric', year: 'numeric' });

  // ── Summary ───────────────────────────────────────────────────────────────
  const summaryHtml = (f.summary && f.summary.length > 50)
    ? `<div class="popup-section popup-summary-section">
         <h4>📋 Episode Summary</h4>
         <div class="popup-summary-text">${f.summary}</div>
       </div>`
    : '';

  // ── Q&A — prefer structured fanQuestions array ───────────────────────────
  let qaHtml = '';
  if (f.fanQuestions && f.fanQuestions.length > 0) {
    qaHtml = f.fanQuestions.map(q => {
      const cr = q.conan_response || {};
      const crText = cr.quote || cr.summary || '';
      const respHtml = crText
        ? `<div class="popup-section">
             <h4 class="popup-response-label">🎙 Conan</h4>
             <div class="popup-question" style="border-left-color:var(--mustgo);">“${crText}”</div>
           </div>`
        : '';
      return `<div class="popup-section">
        <h4>❓ Fan</h4>
        <div class="popup-question">“${q.question}”</div>
      </div>${respHtml}`;
    }).join('');
  } else {
    const question = f.fanQuestion
      ? `<div class="popup-section"><h4>❓ Fan</h4>
         <div class="popup-question">“${f.fanQuestion}”</div></div>`
      : '';
    const response = f.conanResponse
      ? `<div class="popup-section">
         <h4 class="popup-response-label">🎙 Conan</h4>
         <div class="popup-question" style="border-left-color:var(--mustgo);">“${f.conanResponse}”</div></div>`
      : '';
    qaHtml = question + response;
  }

  // ── Highlights — narrative bullets, no category labels or bold titles ───────
  let highlightsHtml = '';
  if (f.highlightsV2 && f.highlightsV2.length > 0) {
    const items = f.highlightsV2.map(h => {
      // Subtle left-border accent by category — colour only, no text label
      const color = HL_CAT_COLOR[h.category] || 'var(--orange)';
      return `<li style="border-left-color:${color}40">${h.summary}</li>`;
    }).join('');
    highlightsHtml = `<div class="popup-section"><h4>⭐ Highlights</h4>
      <ul class="popup-highlights popup-highlights-v2">${items}</ul></div>`;
  } else {
    const hl = (f.highlights || []).map(h => `<li>${h}</li>`).join('');
    highlightsHtml = hl
      ? `<div class="popup-section"><h4>⭐ Highlights</h4>
         <ul class="popup-highlights">${hl}</ul></div>`
      : '';
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
      ${badge}
      ${shareBtn}
    </div>
    <div class="popup-name">${f.fullName || f.name}</div>
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

// ============================================================
// MAPLIBRE GL JS MAP
// ============================================================

// Build GeoJSON FeatureCollection from FANS array
const _fanFeatures = FANS.filter(f => f.coords).map(f => ({
  type: 'Feature',
  geometry: {
    type: 'Point',
    coordinates: [f.coords[1], f.coords[0]]   // MapLibre is [lng, lat]
  },
  properties: {
    slug:   f.slug   || '',
    mustGo: f.mustGo ? 1 : 0
  }
}));

// SVG pin factory — returns an SVG string
function _pinSvg(color) {
  return `<svg width="28" height="38" viewBox="0 0 28 38" xmlns="http://www.w3.org/2000/svg">
    <path d="M14 0C6.27 0 0 6.27 0 14c0 9.63 14 24 14 24S28 23.63 28 14C28 6.27 21.73 0 14 0z"
          fill="${color}" stroke="rgba(0,0,0,0.4)" stroke-width="1.5"/>
    <circle cx="14" cy="14" r="6" fill="rgba(255,255,255,0.9)"/>
  </svg>`;
}

function _svgBlobUrl(svgStr) {
  const blob = new Blob([svgStr], { type: 'image/svg+xml' });
  return URL.createObjectURL(blob);
}

// ── Map ──────────────────────────────────────────────────────────────────────
const map = new maplibregl.Map({
  container:          'map',
  style:              'https://tiles.openfreemap.org/styles/dark',
  center:             [10, 20],
  zoom:               2,
  minZoom:            2,
  maxZoom:            18,
  maxBounds:          [[-180, -85], [180, 85]],
  cooperativeGestures: true,
  attributionControl:  false
});

// Minimal, unobtrusive attribution
map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');

// Active popup reference
let _popup = null;

function _closePopup() {
  if (_popup) { _popup.remove(); _popup = null; }
}

function _showMapPopup(fan) {
  _closePopup();
  const [lat, lng] = fan.coords;
  _popup = new maplibregl.Popup({
    closeButton:  true,
    closeOnClick: false,
    maxWidth:     '560px',
    className:    'fan-popup'
  })
  .setLngLat([lng, lat])
  .setHTML(buildPopupHTML(fan))
  .addTo(map);

  _popup.on('close', () => { clearUrl(); _popup = null; });
}

// ── Load handler: colours + sources + layers ─────────────────────────────────
map.on('load', function () {

  // 1 ── Override ocean / water to design token ────────────────────────────
  (map.getStyle().layers || []).forEach(layer => {
    try {
      if (layer.type === 'background') {
        map.setPaintProperty(layer.id, 'background-color', OCEAN);
      }
      if (layer.type === 'fill') {
        const id = layer.id.toLowerCase();
        if (id.includes('water') || id === 'ocean') {
          map.setPaintProperty(layer.id, 'fill-color', OCEAN);
        }
      }
      if (layer.type === 'line') {
        const id = layer.id.toLowerCase();
        if (id.includes('waterway') || id.includes('river') || id.includes('water')) {
          map.setPaintProperty(layer.id, 'line-color', OCEAN);
        }
      }
    } catch (_) { /* layer might not support this property */ }
  });

  // 2 ── Load SVG pin images ────────────────────────────────────────────────
  function _loadPinImage(id, color, cb) {
    const url = _svgBlobUrl(_pinSvg(color));
    const img = new Image(28, 38);
    img.onload = function () {
      if (!map.hasImage(id)) map.addImage(id, img, { pixelRatio: 2 });
      URL.revokeObjectURL(url);
      cb();
    };
    img.src = url;
  }

  let _imagesLoaded = 0;
  function _onImageLoaded() {
    _imagesLoaded++;
    if (_imagesLoaded === 2) _initLayers();
  }
  _loadPinImage('pin-fan',    ORANGE,   _onImageLoaded);
  _loadPinImage('pin-mustgo', MUSTGO_C, _onImageLoaded);
});

// ── Build map layers once both pin images are ready ───────────────────────────
function _initLayers() {

  // ── Fan GeoJSON source with built-in clustering ──────────────────────────
  map.addSource('fans', {
    type:          'geojson',
    data:          { type: 'FeatureCollection', features: _fanFeatures },
    cluster:       true,
    clusterMaxZoom: 10,
    clusterRadius:  50
  });

  // Cluster circles
  map.addLayer({
    id:     'clusters',
    type:   'circle',
    source: 'fans',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': [
        'step', ['get', 'point_count'],
        ORANGE,       5,
        '#e85600',   15,
        '#c94e12'
      ],
      'circle-radius': ['step', ['get', 'point_count'], 18, 5, 24, 15, 30],
      'circle-stroke-width': 2,
      'circle-stroke-color': 'rgba(255,255,255,0.25)'
    }
  });

  // Cluster count labels
  map.addLayer({
    id:     'cluster-count',
    type:   'symbol',
    source: 'fans',
    filter: ['has', 'point_count'],
    layout: {
      'text-field':            '{point_count_abbreviated}',
      'text-font':             ['Noto Sans Bold', 'Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size':             12,
      'text-allow-overlap':    true
    },
    paint: {
      'text-color': '#ffffff'
    }
  });

  // Individual fan pins
  map.addLayer({
    id:     'unclustered-point',
    type:   'symbol',
    source: 'fans',
    filter: ['!', ['has', 'point_count']],
    layout: {
      'icon-image':           ['case', ['==', ['get', 'mustGo'], 1], 'pin-mustgo', 'pin-fan'],
      'icon-size':             1,
      'icon-anchor':           'bottom',
      'icon-allow-overlap':    true,
      'icon-ignore-placement': true
    }
  });

  // ── Click: cluster → zoom in ─────────────────────────────────────────────
  map.on('click', 'clusters', function (e) {
    const feat      = e.features[0];
    const clusterId = feat.properties.cluster_id;
    map.getSource('fans').getClusterExpansionZoom(clusterId, function (err, zoom) {
      if (err) return;
      map.easeTo({ center: feat.geometry.coordinates, zoom: zoom + 0.5, duration: 600 });
    });
  });

  // ── Click: individual pin ────────────────────────────────────────────────
  map.on('click', 'unclustered-point', function (e) {
    const slug = e.features[0].properties.slug;
    const fan  = FANS.find(f => f.slug === slug);
    if (!fan) return;
    if (navigator.vibrate) navigator.vibrate([10]);
    syncUrl(fan.slug);
    if (isMobile()) openBottomSheet(fan);
    else            _showMapPopup(fan);
  });

  // ── Cursor ───────────────────────────────────────────────────────────────
  ['clusters', 'unclustered-point'].forEach(id => {
    map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', id, () => { map.getCanvas().style.cursor = '';        });
  });

  // ── Deep-link: ?fan=slug ─────────────────────────────────────────────────
  (function handleDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const slug   = params.get('fan');
    if (!slug) return;
    const fan = FANS.find(f => f.slug === slug);
    if (!fan || !fan.coords) return;
    const [lat, lng] = fan.coords;
    setTimeout(function () {
      map.flyTo({ center: [lng, lat], zoom: 7, duration: 1200 });
      map.once('moveend', function () {
        syncUrl(slug);
        if (isMobile()) openBottomSheet(fan);
        else            _showMapPopup(fan);
      });
    }, 300);
  })();
}

// ── Legend toggle ─────────────────────────────────────────────────────────────
function toggleLegend() {
  const legend = document.getElementById('mapLegend');
  if (legend) legend.classList.toggle('collapsed');
}

(function initLegend() {
  if (window.innerWidth < 640) {
    const legend = document.getElementById('mapLegend');
    if (legend) legend.classList.add('collapsed');
  }
})();

// ── Fly to fan (from table row / episode list) ────────────────────────────────
function flyToFan(slug) {
  const fan = FANS.find(f => f.slug === slug);
  if (!fan || !fan.coords) return;
  if (navigator.vibrate) navigator.vibrate([10]);
  document.getElementById('map').scrollIntoView({ behavior: 'smooth', block: 'center' });
  const [lat, lng] = fan.coords;
  setTimeout(function () {
    map.flyTo({ center: [lng, lat], zoom: 7, duration: 1000 });
    map.once('moveend', function () {
      syncUrl(slug);
      if (isMobile()) openBottomSheet(fan);
      else            _showMapPopup(fan);
    });
  }, 300);
}

// ── Show fan detail (from episode table) ─────────────────────────────────────
function showFanDetail(slug) {
  const f = FANS.find(fan => fan.slug === slug);
  if (!f) return;
  if (navigator.vibrate) navigator.vibrate([10]);
  if (isMobile()) {
    openBottomSheet(f);
  } else {
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
  if (modal)   modal.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
  document.body.style.overflow = '';
}

// ── Choropleth layer ──────────────────────────────────────────────────────────
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

const _fanCountByCountry = {};
FANS.forEach(f => {
  if (f.country && f.country !== 'Unknown')
    _fanCountByCountry[f.country] = (_fanCountByCountry[f.country] || 0) + 1;
});

const _maxFans = Math.max(...Object.values(_fanCountByCountry));

function _choroplethColor(count) {
  if (!count) return 'transparent';
  const t = Math.pow(count / _maxFans, 0.5);
  const a = Math.round((0.10 + t * 0.60) * 255);
  // Returns hex with alpha encoded into rgba-style string
  return `rgba(242,101,34,${(0.10 + t * 0.60).toFixed(2)})`;
}

let _choroplethOn    = false;
let _choroplethReady = false;
let _choroplethPopup = null;

function toggleChoropleth() {
  const btn = document.getElementById('choroplethToggle');

  if (_choroplethOn) {
    if (map.getLayer('choropleth-fill'))   map.setLayoutProperty('choropleth-fill',   'visibility', 'none');
    if (map.getLayer('choropleth-border')) map.setLayoutProperty('choropleth-border', 'visibility', 'none');
    _choroplethOn = false;
    if (btn) { btn.classList.remove('active'); btn.textContent = '🗺️ Fan Density'; }
    return;
  }

  if (_choroplethReady) {
    if (map.getLayer('choropleth-fill'))   map.setLayoutProperty('choropleth-fill',   'visibility', 'visible');
    if (map.getLayer('choropleth-border')) map.setLayoutProperty('choropleth-border', 'visibility', 'visible');
    _choroplethOn = true;
    if (btn) { btn.classList.add('active'); btn.textContent = '✖ Hide Density'; }
    return;
  }

  // First time — fetch TopoJSON and build layers
  if (btn) btn.textContent = 'Loading…';
  fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
    .then(r => r.json())
    .then(function (topo) {
      // Embed ISO numeric + name in properties for easy expression access
      const geojson = topojson.feature(topo, topo.objects.countries);
      geojson.features = geojson.features.map(function (feat) {
        const isoNum = parseInt(feat.id, 10);
        const name   = ISO_NAMES[isoNum] || '';
        const count  = name ? (_fanCountByCountry[name] || 0) : 0;
        return Object.assign({}, feat, {
          properties: { isoNum, name, count }
        });
      });

      // Build fill-color match expression
      const colorExpr = ['match', ['get', 'count']];
      const seen = new Set();
      Object.values(_fanCountByCountry).forEach(c => {
        if (!seen.has(c)) {
          seen.add(c);
          colorExpr.push(c, _choroplethColor(c));
        }
      });
      colorExpr.push('transparent');

      // Simpler: interpolate on 'count' property
      const fillExpr = [
        'case',
        ['>', ['get', 'count'], 0],
        [
          'interpolate', ['linear'], ['get', 'count'],
          1,  'rgba(242,101,34,0.15)',
          3,  'rgba(242,101,34,0.30)',
          8,  'rgba(242,101,34,0.50)',
          20, 'rgba(242,101,34,0.70)'
        ],
        'transparent'
      ];

      if (!map.getSource('choropleth')) {
        map.addSource('choropleth', { type: 'geojson', data: geojson });
      }

      if (!map.getLayer('choropleth-fill')) {
        map.addLayer({
          id:     'choropleth-fill',
          type:   'fill',
          source: 'choropleth',
          paint:  { 'fill-color': fillExpr, 'fill-opacity': 1 }
        }, 'clusters');   // insert below markers
      }

      if (!map.getLayer('choropleth-border')) {
        map.addLayer({
          id:     'choropleth-border',
          type:   'line',
          source: 'choropleth',
          filter: ['>', ['get', 'count'], 0],
          paint:  { 'line-color': 'rgba(242,101,34,0.50)', 'line-width': 0.6 }
        }, 'clusters');
      }

      // Hover tooltip
      map.on('mousemove', 'choropleth-fill', function (e) {
        const feat = e.features && e.features[0];
        if (!feat || !feat.properties.count) return;
        const { name, count } = feat.properties;
        if (_choroplethPopup) _choroplethPopup.remove();
        _choroplethPopup = new maplibregl.Popup({
          closeButton: false, closeOnClick: false, className: 'choropleth-tooltip-popup'
        })
        .setLngLat(e.lngLat)
        .setHTML(`<strong>${name}</strong><br>${count} fan${count !== 1 ? 's' : ''}`)
        .addTo(map);
      });
      map.on('mouseleave', 'choropleth-fill', function () {
        if (_choroplethPopup) { _choroplethPopup.remove(); _choroplethPopup = null; }
      });

      _choroplethReady = true;
      _choroplethOn    = true;
      if (btn) { btn.classList.add('active'); btn.textContent = '✖ Hide Density'; }
    })
    .catch(function () {
      if (btn) btn.textContent = '🗺️ Fan Density';
    });
}

// ── Stats bar ─────────────────────────────────────────────────────────────────
(function updateStats() {
  const countries  = [...new Set(FANS.map(f => f.country))].filter(c => c !== 'Unknown');
  const mustGoFans = FANS.filter(f => f.mustGo);
  document.getElementById('statFans').textContent      = FANS.length;
  document.getElementById('statCountries').textContent = countries.length;
  document.getElementById('statMustGo').textContent    = mustGoFans.length;
  document.getElementById('statWorldPct').textContent  = Math.round(countries.length / 195 * 100) + '%';
})();

// ── DOM ready: wire up close buttons / modal ──────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const overlay  = document.getElementById('sheetOverlay');
  const closeBtn = document.getElementById('sheetClose');
  if (overlay)  overlay.addEventListener('click',  function () { closeBottomSheet(); clearUrl(); });
  if (closeBtn) closeBtn.addEventListener('click',  function () { closeBottomSheet(); clearUrl(); });

  const fanModalOverlay = document.getElementById('fanModalOverlay');
  const fanModalClose   = document.getElementById('fanModalClose');
  if (fanModalOverlay) fanModalOverlay.addEventListener('click', closeFanModal);
  if (fanModalClose)   fanModalClose.addEventListener('click', closeFanModal);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeFanModal();
  });
});
