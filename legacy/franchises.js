const franchiseList = document.querySelector('#franchiseList');
const franchiseCount = document.querySelector('#franchiseCount');
const franchiseSearch = document.querySelector('#franchiseSearch');
const collapseAllSeries = document.querySelector('#collapseAllSeries');
const franchiseSourceNote = document.querySelector('#franchiseSourceNote');
const releaseFormatter = new Intl.DateTimeFormat('en', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
let allSeries = [];
let masteredIds = new Set();

function externalLink(href, className = '') {
  const link = document.createElement('a');
  link.href = href;
  link.target = '_blank';
  link.rel = 'noreferrer';
  if (className) link.className = className;
  return link;
}

function text(value, fallback = '—') {
  const result = String(value ?? '').trim();
  return result || fallback;
}

function formatRelease(game) {
  if (!game.releaseDate) return 'Release date unavailable';
  const raw = String(game.releaseDate);
  const granularity = game.releaseGranularity || 'day';
  if (granularity === 'year') return raw.slice(0, 4);
  if (granularity === 'month') {
    const date = new Date(`${raw.slice(0, 7)}-01T00:00:00Z`);
    return Number.isNaN(date.getTime()) ? raw : new Intl.DateTimeFormat('en', { year: 'numeric', month: 'short', timeZone: 'UTC' }).format(date);
  }
  const date = new Date(`${raw.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? raw : releaseFormatter.format(date);
}

function createGame(game) {
  const item = document.createElement('li');
  item.className = 'franchise-game';
  if (masteredIds.has(Number(game.id))) item.classList.add('is-mastered');
  if (!game.hasSet) item.classList.add('has-no-set');

  const status = document.createElement('span');
  status.className = 'franchise-game-status';
  status.setAttribute('aria-label', masteredIds.has(Number(game.id)) ? 'Mastered' : 'Not mastered');
  status.textContent = masteredIds.has(Number(game.id)) ? '✓' : '○';

  const iconWrap = game.url ? externalLink(game.url, 'franchise-game-icon') : document.createElement('span');
  if (!game.url) iconWrap.className = 'franchise-game-icon';

  if (game.icon) {
    const image = document.createElement('img');
    image.src = game.icon;
    image.alt = '';
    image.loading = 'lazy';
    image.width = 40;
    image.height = 40;
    iconWrap.append(image);
  }

  const copy = document.createElement('div');
  copy.className = 'franchise-game-copy';

  const title = game.url ? externalLink(game.url, 'franchise-game-title') : document.createElement('span');
  if (!game.url) title.className = 'franchise-game-title';
  title.textContent = text(game.name, `Game ${game.id}`);

  const meta = document.createElement('span');
  meta.className = 'franchise-game-meta';
  const noSetSuffix = game.hasSet ? '' : ' · No achievement set';
  meta.textContent = `${text(game.console, 'Unknown console')} · ${formatRelease(game)}${noSetSuffix}`;

  copy.append(title, meta);
  item.append(status, iconWrap, copy);
  return item;
}

function createSeriesCard(series) {
  const masteredCount = series.games.filter(game => masteredIds.has(Number(game.id))).length;
  const card = document.createElement('article');
  card.className = 'franchise-card is-collapsed';
  card.dataset.search = `${series.name} ${series.games.map(game => game.name).join(' ')}`.toLowerCase();

  const button = document.createElement('button');
  button.className = 'franchise-card-header';
  button.type = 'button';
  button.setAttribute('aria-expanded', 'false');

  const heading = document.createElement('div');
  heading.className = 'franchise-card-heading';

  const titleRow = document.createElement('div');
  titleRow.className = 'franchise-card-title-row';

  const title = document.createElement('h2');
  title.textContent = series.name;

  const progress = document.createElement('span');
  progress.className = 'franchise-progress';
  progress.textContent = `${masteredCount} / ${series.games.length} mastered`;
  titleRow.append(title, progress);

  const subtitle = document.createElement('p');
  const setCount = series.games.filter(game => game.hasSet).length;
  subtitle.textContent = `${series.games.length} games · ${setCount} with achievements`;
  heading.append(titleRow, subtitle);

  const chevron = document.createElement('span');
  chevron.className = 'franchise-chevron';
  chevron.textContent = '+';
  chevron.setAttribute('aria-hidden', 'true');
  button.append(heading, chevron);

  const body = document.createElement('div');
  body.className = 'franchise-card-body';
  body.hidden = true;

  if (series.hubUrl) {
    const hub = externalLink(series.hubUrl, 'franchise-hub-link');
    hub.textContent = 'View series hub on RetroAchievements ↗';
    body.append(hub);
  }

  const list = document.createElement('ol');
  list.className = 'franchise-game-list';
  series.games.forEach(game => list.append(createGame(game)));
  body.append(list);

  button.addEventListener('click', () => {
    const expanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!expanded));
    body.hidden = expanded;
    card.classList.toggle('is-collapsed', expanded);
    chevron.textContent = expanded ? '+' : '−';
  });

  card.append(button, body);
  return card;
}

function renderSeries() {
  const query = franchiseSearch.value.trim().toLowerCase();
  franchiseList.replaceChildren();
  const visible = allSeries.filter(series => !query || series.search.includes(query));

  if (!visible.length) {
    const empty = document.createElement('p');
    empty.className = 'franchise-empty';
    empty.textContent = query ? 'No tracked series matches that search.' : 'No series catalog has been generated yet.';
    franchiseList.append(empty);
  } else {
    const fragment = document.createDocumentFragment();
    visible.forEach(item => fragment.append(item.card));
    franchiseList.append(fragment);
  }

  franchiseCount.textContent = `${allSeries.length} ${allSeries.length === 1 ? 'series' : 'series'}`;
}

async function loadFranchises() {
  const [franchiseResponse, gamesResponse] = await Promise.all([
    fetch('franchises.json', { cache: 'no-store' }),
    fetch('mastered-games.json', { cache: 'no-store' })
  ]);

  if (!franchiseResponse.ok || !gamesResponse.ok) throw new Error('Could not load franchise data');

  const data = await franchiseResponse.json();
  const gameData = await gamesResponse.json();
  masteredIds = new Set((gameData.mastered || []).map(game => Number(game.id)));

  const sourceSeries = Array.isArray(data.series) ? data.series : [];
  allSeries = sourceSeries
    .filter(series => {
      const gameMatch = (series.games || []).some(game => masteredIds.has(Number(game.id)));
      const triggerMatch = (series.triggerMasteredGameIds || []).some(id => masteredIds.has(Number(id)));
      return gameMatch || triggerMatch;
    })
    .map(series => ({
      ...series,
      search: `${series.name} ${(series.games || []).map(game => game.name).join(' ')}`.toLowerCase(),
      card: createSeriesCard(series)
    }))
    .sort((a, b) => {
      const aMastered = (a.games || []).filter(game => masteredIds.has(Number(game.id))).length;
      const bMastered = (b.games || []).filter(game => masteredIds.has(Number(game.id))).length;
      if (bMastered !== aMastered) return bMastered - aMastered;
      return a.name.localeCompare(b.name);
    });

  renderSeries();
  franchiseSourceNote.textContent = 'Mastery checks and game metadata update automatically. Series membership is curated manually from RetroAchievements Series hubs.';
}

franchiseSearch.addEventListener('input', renderSeries);

collapseAllSeries.addEventListener('click', () => {
  allSeries.forEach(item => {
    const button = item.card.querySelector('.franchise-card-header');
    const body = item.card.querySelector('.franchise-card-body');
    const chevron = item.card.querySelector('.franchise-chevron');

    if (button) button.setAttribute('aria-expanded', 'false');
    if (body) body.hidden = true;
    if (chevron) chevron.textContent = '+';
    item.card.classList.add('is-collapsed');
  });
});

loadFranchises().catch(error => {
  console.error(error);
  franchiseCount.textContent = 'Error loading series';
  franchiseSourceNote.textContent = 'Could not load the franchise catalog.';
});
