// ============================================================
// CHARTS (Chart.js)
// ============================================================
Chart.defaults.color       = '#7a8299';
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, Segoe UI, Arial';

const _orange  = '#F26522';
const _bg2     = '#181c24';
const _gridClr = '#2a3040';
const _lblClr  = '#7a8299';

// ── 1. Top Countries (expandable) ────────────────────────────────────────────
(function chartCountries() {
  const cntMap = {};
  FANS.forEach(f => {
    if (f.country && f.country !== 'Unknown')
      cntMap[f.country] = (cntMap[f.country] || 0) + 1;
  });
  const allSorted = Object.entries(cntMap).sort((a, b) => b[1] - a[1]);
  const DEFAULT_N = 10;
  let showAll = false;

  function getSlice() {
    return showAll ? allSorted : allSorted.slice(0, DEFAULT_N);
  }

  const canvas = document.getElementById('chartCountries');
  // Set initial height
  canvas.style.maxHeight = '280px';

  const chart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: getSlice().map(x => x[0]),
      datasets: [{
        data: getSlice().map(x => x[1]),
        backgroundColor: getSlice().map((_, i) => `rgba(242,101,34,${Math.max(0.3, 1 - i * 0.05)})`),
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: _lblClr, stepSize: 1 }, grid: { color: _gridClr } },
        y: { ticks: { color: _lblClr }, grid: { color: _gridClr } }
      }
    }
  });

  // Inject expand button below chart card
  const card = canvas.closest('.chart-card');
  if (card && allSorted.length > DEFAULT_N) {
    const btn = document.createElement('button');
    btn.className = 'chart-expand-btn';
    btn.textContent = `Show all ${allSorted.length} countries`;
    card.appendChild(btn);

    btn.addEventListener('click', function() {
      showAll = !showAll;
      const slice = getSlice();
      chart.data.labels = slice.map(x => x[0]);
      chart.data.datasets[0].data = slice.map(x => x[1]);
      chart.data.datasets[0].backgroundColor = slice.map((_, i) =>
        `rgba(242,101,34,${Math.max(0.3, 1 - i * 0.05)})`);
      // Resize canvas height proportionally
      canvas.style.maxHeight = showAll ? (slice.length * 28) + 'px' : '280px';
      chart.resize();
      chart.update();
      btn.textContent = showAll
        ? `Show top ${DEFAULT_N} only`
        : `Show all ${allSorted.length} countries`;
    });
  }
})();

// ── 2. Continents ────────────────────────────────────────────────────────────
(function chartContinents() {
  const CONTINENT = {
    'United States': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
    'United Kingdom': 'Europe', 'Ireland': 'Europe', 'France': 'Europe', 'Germany': 'Europe',
    'Spain': 'Europe', 'Portugal': 'Europe', 'Netherlands': 'Europe', 'Finland': 'Europe',
    'Austria': 'Europe', 'Greece': 'Europe', 'Croatia': 'Europe', 'Norway': 'Europe',
    'Ukraine': 'Europe', 'Iceland': 'Europe', 'Slovenia': 'Europe', 'Hungary': 'Europe',
    'Belgium': 'Europe', 'Switzerland': 'Europe',
    'India': 'Asia', 'Philippines': 'Asia', 'Thailand': 'Asia', 'Japan': 'Asia',
    'Singapore': 'Asia', 'Kyrgyzstan': 'Asia', 'Kazakhstan': 'Asia',
    'Lebanon': 'Asia', 'Iran': 'Asia', 'Israel': 'Asia', 'Turkey': 'Asia',
    'Egypt': 'Africa', 'Ethiopia': 'Africa', 'Kenya': 'Africa', 'Morocco': 'Africa',
    'South Africa': 'Africa',
    'Colombia': 'South America', 'Brazil': 'South America', 'Argentina': 'South America',
    'Australia': 'Oceania', 'New Zealand': 'Oceania',
    'Antarctica': 'Antarctica',
  };
  const regionMap = { 'North America': 0, 'Europe': 0, 'Asia': 0,
                      'Oceania': 0, 'South America': 0, 'Africa': 0, 'Antarctica': 0 };
  FANS.forEach(f => {
    const r = CONTINENT[f.country];
    if (r && r in regionMap) regionMap[r]++;
  });
  const entries = Object.entries(regionMap).filter(x => x[1] > 0);
  new Chart(document.getElementById('chartRegions'), {
    type: 'pie',
    data: {
      labels: entries.map(x => x[0]),
      datasets: [{
        data: entries.map(x => x[1]),
        backgroundColor: ['#F26522', '#3498db', '#27ae60', '#f39c12', '#e94560', '#9b59b6', '#adb5c7'],
        borderWidth: 2,
        borderColor: _bg2
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom', labels: { color: _lblClr, padding: 8, font: { size: 11 } } } }
    }
  });
})();

// ── 3. Occupation categories ──────────────────────────────────────────────────
(function chartOccupations() {
  const occMap = {};
  FANS.forEach(f => { occMap[f.occupationCategory] = (occMap[f.occupationCategory] || 0) + 1; });
  const entries  = Object.entries(occMap).sort((a, b) => b[1] - a[1]);
  const occColors = ['#F26522','#0057B8','#3498db','#27ae60','#f39c12',
                     '#9b59b6','#1abc9c','#e67e22','#e74c3c','#2980b9','#8e44ad','#16a085'];
  new Chart(document.getElementById('chartOccupations'), {
    type: 'doughnut',
    data: {
      labels: entries.map(x => x[0]),
      datasets: [{
        data: entries.map(x => x[1]),
        backgroundColor: occColors,
        borderWidth: 2,
        borderColor: _bg2
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom', labels: { color: _lblClr, padding: 10, font: { size: 11 } } } }
    }
  });
})();

// ── 4. Episodes over time ─────────────────────────────────────────────────────
(function chartYears() {
  const yearMap = {};
  FANS.forEach(f => { const y = f.date.substring(0, 4); yearMap[y] = (yearMap[y] || 0) + 1; });
  const entries = Object.entries(yearMap).sort();
  new Chart(document.getElementById('chartYears'), {
    type: 'line',
    data: {
      labels: entries.map(x => x[0]),
      datasets: [{
        data: entries.map(x => x[1]),
        borderColor: _orange,
        backgroundColor: 'rgba(242,101,34,0.15)',
        pointBackgroundColor: _orange,
        pointRadius: 5,
        tension: 0.3,
        fill: true
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: _lblClr }, grid: { color: _gridClr } },
        y: { ticks: { color: _lblClr, stepSize: 5 }, grid: { color: _gridClr } }
      }
    }
  });
})();
