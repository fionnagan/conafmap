// ============================================================
// TABLE + FILTERS
// ============================================================
let currentSort = { key: 'date', asc: false };
let filtered    = [...FANS];

function populateFilters() {
  const cs      = document.getElementById('countryFilter');
  const cats    = document.getElementById('catFilter');
  const countries = [...new Set(FANS.map(f => f.country))]
    .filter(c => c && c !== 'Unknown').sort();
  const catList = [...new Set(FANS.map(f => f.occupationCategory))].sort();
  countries.forEach(c => {
    const o = document.createElement('option'); o.value = c; o.textContent = c; cs.appendChild(o);
  });
  catList.forEach(c => {
    const o = document.createElement('option'); o.value = c; o.textContent = c; cats.appendChild(o);
  });
}

function applyFilters() {
  const q       = document.getElementById('searchInput').value.toLowerCase();
  const country = document.getElementById('countryFilter').value;
  const cat     = document.getElementById('catFilter').value;
  const mg      = document.getElementById('mustgoFilter').value;
  filtered = FANS.filter(f => {
    if (q && ![f.name, f.fullName, f.location, f.displayLocation, f.occupation,
               f.episode, f.occupationCategory, f.fanQuestion, f.conanResponse,
               f.topic, (f.highlights || []).join(' ')]
              .some(s => (s || '').toLowerCase().includes(q))) return false;
    if (country && f.country !== country)       return false;
    if (cat     && f.occupationCategory !== cat) return false;
    if (mg === 'podcast' && f.mustGo)            return false;
    if (mg === 'hbo'     && !f.mustGo)           return false;
    return true;
  });
  sortAndRender();
}

function sortTable(key) {
  if (currentSort.key === key) currentSort.asc = !currentSort.asc;
  else { currentSort.key = key; currentSort.asc = true; }
  sortAndRender();
}

function sortAndRender() {
  const { key, asc } = currentSort;
  filtered.sort((a, b) => {
    const av = a[key] || '', bv = b[key] || '';
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  // Update sort indicators on all sortable <th>s
  document.querySelectorAll('th[onclick]').forEach(function(th) {
    th.classList.remove('sorted', 'sorted-asc', 'sorted-desc');
    const m = th.getAttribute('onclick').match(/sortTable\('(\w+)'\)/);
    if (m && m[1] === key) {
      th.classList.add('sorted', asc ? 'sorted-asc' : 'sorted-desc');
    }
  });
  renderTable();
}

// ── Heard (LocalStorage) ─────────────────────────────────────────────────────
const HEARD_KEY = 'conaf_heard';

function getHeardMap() {
  try { return JSON.parse(localStorage.getItem(HEARD_KEY) || '{}'); }
  catch(e) { return {}; }
}

function toggleHeard(slug, btn) {
  const heard = getHeardMap();
  if (heard[slug]) {
    delete heard[slug];
    btn.classList.remove('heard');
    btn.title = 'Mark as heard';
  } else {
    heard[slug] = true;
    btn.classList.add('heard');
    btn.title = 'Heard!';
    if (navigator.vibrate) navigator.vibrate([8]);
  }
  try { localStorage.setItem(HEARD_KEY, JSON.stringify(heard)); } catch(e) {}
  // Update total heard count in stats bar if present
  _updateHeardStat();
}

function _updateHeardStat() {
  const count = Object.keys(getHeardMap()).length;
  const el = document.getElementById('statHeard');
  if (el) el.textContent = count;
}

function renderTable() {
  const tbody = document.getElementById('epTableBody');
  document.getElementById('tableCount').textContent  = `Showing ${filtered.length} of ${FANS.length} fan episodes`;
  document.getElementById('filterCount').textContent = `${filtered.length} results`;
  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="no-results">No episodes match your filters.</td></tr>';
    return;
  }

  const rows = [];
  const heard = getHeardMap();

  filtered.forEach((f, idx) => {
    const d = new Date(f.date + 'T12:00:00').toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', year: 'numeric' });

    // Episode cell: title link + Must Go badge inline
    let mgBadge = '';
    if (f.mustGo) {
      const sl = f.mustGoSeason ? ` S${f.mustGoSeason}` : '';
      mgBadge = `<span class="badge-mustgo">Must Go${sl}</span>`;
    }
    const epTitle = f.teamcocoUrl
      ? `<a href="${f.teamcocoUrl}" target="_blank" style="color:var(--orange);text-decoration:none;">${f.episode}</a>`
      : f.episode;
    const epCell = `<td class="td-ep">${epTitle} ${mgBadge}</td>`;

    // Q&A chevron cell — only show when real transcript data exists
    const hasQ = !!f.fanQuestion;
    const hasR = !!f.conanResponse;
    let qCell = '<td></td>';
    if (hasQ || hasR) {
      qCell = `<td class="q-chevron-cell" data-idx="${idx}" onclick="toggleQRow(this, ${idx})">
        <span class="chevron">\u203A</span>
      </td>`;
    }

    const rowClick = (hasQ || hasR)
      ? `onclick="(function(e){if(e.target.closest('a')||e.target.closest('.td-name-link'))return;if(typeof isMobile==='function'&&isMobile()){var c=document.querySelector('.q-chevron-cell[data-idx=\\'${idx}\\']');if(c)toggleQRow(c,${idx});}})(event)"`
      : '';
    rows.push(`<tr class="fan-row" data-idx="${idx}" ${rowClick}>
      <td class="td-date">${d}</td>
      <td><div class="td-name td-name-link" onclick="showFanDetail('${f.slug}')" title="View fan details">${f.fullName || f.name}</div></td>
      <td class="td-loc">${f.displayLocation || f.location}</td>
      <td class="td-occ">${f.occupation.substring(0, 60)}${f.occupation.length > 60 ? '\u2026' : ''}</td>
      ${epCell}
      ${qCell}
    </tr>`);
  });

  tbody.innerHTML = rows.join('');
}

// ── Q&A row expand / collapse ─────────────────────────────────────────────────
function toggleQRow(cell, idx) {
  const tr = cell.closest('tr');
  const isOpen = cell.classList.contains('open');

  // Remove any other open detail rows
  document.querySelectorAll('.q-detail-row').forEach(r => r.remove());
  document.querySelectorAll('.q-chevron-cell.open').forEach(c => c.classList.remove('open'));

  if (isOpen) return; // was open → just close

  const f = filtered[idx];
  const qHtml = f.fanQuestion
    ? `<div class="q-detail-fan">\u201c${f.fanQuestion}\u201d</div>`
    : '';
  const rHtml = f.conanResponse
    ? `<div class="q-detail-conan">\u201c${f.conanResponse}\u201d</div>`
    : '';

  if (!qHtml && !rHtml) return;

  const detailTr = document.createElement('tr');
  detailTr.className = 'q-detail-row';
  detailTr.innerHTML = `<td colspan="6">
    <div class="q-detail-inner">${qHtml}${rHtml}</div>
  </td>`;
  tr.after(detailTr);
  cell.classList.add('open');
}

function resetFilters() {
  document.getElementById('searchInput').value    = '';
  document.getElementById('countryFilter').value  = '';
  document.getElementById('catFilter').value      = '';
  document.getElementById('mustgoFilter').value   = '';
  filtered = [...FANS];
  sortAndRender();
}

// ── Mobile filter toggle ──────────────────────────────────────────────────────
(function initFilterToggle() {
  const toggleBtn = document.getElementById('filterToggleBtn');
  const controls  = document.getElementById('filterControls');
  const badge     = document.getElementById('filterCountBadge');
  if (!toggleBtn || !controls) return;

  toggleBtn.addEventListener('click', function() {
    const collapsed = controls.classList.toggle('collapsed');
    toggleBtn.setAttribute('aria-expanded', String(!collapsed));
  });

  // Update active-filter badge count
  function updateBadge() {
    const q  = document.getElementById('searchInput').value;
    const ct = document.getElementById('countryFilter').value;
    const ca = document.getElementById('catFilter').value;
    const mg = document.getElementById('mustgoFilter').value;
    const n  = [q, ct, ca, mg].filter(Boolean).length;
    if (badge) badge.textContent = n > 0 ? n : '';
  }
  ['searchInput', 'countryFilter', 'catFilter', 'mustgoFilter'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.addEventListener('input', updateBadge); el.addEventListener('change', updateBadge); }
  });
})();

['searchInput', 'countryFilter', 'catFilter', 'mustgoFilter'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('input',  applyFilters);
  el.addEventListener('change', applyFilters);
});


populateFilters();
sortAndRender();
_updateHeardStat();
