const consoleChart = document.querySelector('#consoleChart');
const genreChart = document.querySelector('#genreChart');
const timelineChart = document.querySelector('#timelineChart');
const franchiseChart = document.querySelector('#franchiseChart');
const statsUpdated = document.querySelector('#statsUpdated');
const statsSourceNote = document.querySelector('#statsSourceNote');

const statMastered = document.querySelector('#statMastered');
const statConsoles = document.querySelector('#statConsoles');
const statGenres = document.querySelector('#statGenres');
const statSeries = document.querySelector('#statSeries');

const dateFormatter = new Intl.DateTimeFormat('en', { year: 'numeric', month: 'short', day: 'numeric' });
const monthFormatter = new Intl.DateTimeFormat('en', { year: 'numeric', month: 'short' });

function clean(value, fallback = 'Unknown') {
  const text = String(value ?? '').trim();
  return text || fallback;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : dateFormatter.format(date);
}

function tally(items, accessor) {
  const counts = new Map();
  for (const item of items) {
    const key = clean(accessor(item));
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}

function renderBars(target, rows, emptyMessage = 'No data yet.') {
  target.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'chart-empty';
    empty.textContent = emptyMessage;
    target.append(empty);
    return;
  }

  const max = Math.max(...rows.map(row => row.value), 1);
  const fragment = document.createDocumentFragment();
  rows.forEach(row => {
    const item = document.createElement('div');
    item.className = 'bar-row';

    const label = document.createElement('span');
    label.className = 'bar-label';
    label.textContent = row.label;
    label.title = row.label;

    const track = document.createElement('div');
    track.className = 'bar-track';
    const fill = document.createElement('div');
    fill.className = 'bar-fill';
    fill.style.width = `${Math.max(2.5, (row.value / max) * 100)}%`;
    track.append(fill);

    const value = document.createElement('strong');
    value.className = 'bar-value';
    value.textContent = row.value;

    item.append(label, track, value);
    fragment.append(item);
  });
  target.append(fragment);
}

function monthKey(date) {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
}

function renderTimeline(target, games) {
  const dated = games
    .map(game => ({ ...game, parsedDate: new Date(game.awardDate) }))
    .filter(game => !Number.isNaN(game.parsedDate.getTime()))
    .sort((a, b) => a.parsedDate - b.parsedDate);

  target.replaceChildren();
  if (!dated.length) {
    target.textContent = 'No dated masteries yet.';
    return;
  }

  const monthly = new Map();
  dated.forEach(game => {
    const key = monthKey(game.parsedDate);
    monthly.set(key, (monthly.get(key) || 0) + 1);
  });

  const first = dated[0].parsedDate;
  const last = dated[dated.length - 1].parsedDate;
  const cursor = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 1));
  const end = new Date(Date.UTC(last.getUTCFullYear(), last.getUTCMonth(), 1));
  const points = [];
  let cumulative = 0;
  while (cursor <= end) {
    const key = monthKey(cursor);
    cumulative += monthly.get(key) || 0;
    points.push({ date: new Date(cursor), value: cumulative });
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }

  const width = 1000;
  const height = 300;
  const padX = 48;
  const padY = 28;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;
  const max = Math.max(points[points.length - 1].value, 1);
  const x = index => padX + (points.length === 1 ? innerW / 2 : index * innerW / (points.length - 1));
  const y = value => padY + innerH - (value / max) * innerH;
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${x(index).toFixed(2)} ${y(point.value).toFixed(2)}`).join(' ');

  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `Cumulative masteries from ${monthFormatter.format(first)} to ${monthFormatter.format(last)}`);

  for (let i = 0; i <= 4; i += 1) {
    const value = Math.round(max * i / 4);
    const gy = y(value);
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', padX); line.setAttribute('x2', width - padX);
    line.setAttribute('y1', gy); line.setAttribute('y2', gy);
    line.setAttribute('class', 'chart-grid-line');
    svg.append(line);

    const label = document.createElementNS(ns, 'text');
    label.setAttribute('x', padX - 12); label.setAttribute('y', gy + 4);
    label.setAttribute('class', 'chart-axis-label'); label.setAttribute('text-anchor', 'end');
    label.textContent = value;
    svg.append(label);
  }

  const pathEl = document.createElementNS(ns, 'path');
  pathEl.setAttribute('d', path);
  pathEl.setAttribute('class', 'chart-line');
  svg.append(pathEl);

  points.forEach((point, index) => {
    if (index !== 0 && index !== points.length - 1 && points.length > 18 && index % Math.ceil(points.length / 8) !== 0) return;
    const label = document.createElementNS(ns, 'text');
    label.setAttribute('x', x(index)); label.setAttribute('y', height - 4);
    label.setAttribute('class', 'chart-axis-label'); label.setAttribute('text-anchor', 'middle');
    label.textContent = monthFormatter.format(point.date);
    svg.append(label);
  });

  const finalDot = document.createElementNS(ns, 'circle');
  finalDot.setAttribute('cx', x(points.length - 1));
  finalDot.setAttribute('cy', y(points[points.length - 1].value));
  finalDot.setAttribute('r', 5);
  finalDot.setAttribute('class', 'chart-dot');
  svg.append(finalDot);

  target.append(svg);
}

function trackedFranchiseCounts(franchiseData, masteredIds) {
  const series = Array.isArray(franchiseData?.series) ? franchiseData.series : [];
  return series.map(item => {
    // triggerMasteredGameIds keeps subset-only discoveries (for example a
    // mastered multiplayer subset) associated with its base-game Series card.
    const ids = new Set([
      ...(Array.isArray(item.games) ? item.games.map(game => Number(game.id)) : []),
      ...(Array.isArray(item.triggerMasteredGameIds) ? item.triggerMasteredGameIds.map(Number) : [])
    ]);
    const value = [...ids].filter(id => masteredIds.has(id)).length;
    return { label: item.name || 'Unnamed series', value };
  }).filter(row => row.value > 0).sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}

async function loadJson(url, fallback = {}) {
  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) return fallback;
    return await response.json();
  } catch {
    return fallback;
  }
}

async function loadStatistics() {
  const [gameData, franchiseData] = await Promise.all([
    loadJson('mastered-games.json', { mastered: [] }),
    loadJson('franchises.json', { series: [] })
  ]);

  const mastered = Array.isArray(gameData.mastered) ? gameData.mastered : [];
  const consoles = tally(mastered, game => game.console);
  const genres = tally(mastered, game => game.genre);
  const masteredIds = new Set(mastered.map(game => Number(game.id)));
  const franchiseCounts = trackedFranchiseCounts(franchiseData, masteredIds);

  statMastered.textContent = mastered.length;
  statConsoles.textContent = consoles.length;
  statGenres.textContent = genres.length;
  statSeries.textContent = franchiseCounts.length;

  renderBars(consoleChart, consoles);
  renderBars(genreChart, genres);
  renderTimeline(timelineChart, mastered);
  renderBars(franchiseChart, franchiseCounts, 'No tracked series data yet.');

  statsUpdated.textContent = gameData.generatedAt ? `Updated ${formatDate(gameData.generatedAt)}` : 'Waiting for data';
  statsSourceNote.textContent = 'Console, genre, and timeline charts update automatically from mastered-games.json. Franchise statistics use the manually mapped RA Series hubs, whose game rosters refresh automatically.';
}

loadStatistics().catch(error => {
  console.error(error);
  statsUpdated.textContent = 'Error loading statistics';
});
