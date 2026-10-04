const masteredBody = document.querySelector('#masteredGamesBody');
const beatenBody = document.querySelector('#beatenGamesBody');
const masteredCount = document.querySelector('#masteredCount');
const beatenCount = document.querySelector('#beatenCount');
const gamesCount = document.querySelector('#gamesCount');
const sourceNote = document.querySelector('#gamesSourceNote');

const dateFormatter = new Intl.DateTimeFormat('en', {
  year: 'numeric',
  month: 'short',
  day: 'numeric'
});

function text(value, fallback = '—') {
  const result = String(value ?? '').trim();
  return result || fallback;
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? text(value) : dateFormatter.format(date);
}

function formatDuration(seconds) {
  const numeric = Number(seconds);
  if (!Number.isFinite(numeric) || numeric < 0) return '—';

  let remaining = Math.round(numeric);
  const hours = Math.floor(remaining / 3600);
  remaining %= 3600;
  const minutes = Math.floor(remaining / 60);
  const secs = remaining % 60;

  const parts = [];
  if (hours) parts.push(`${hours}h`);
  if (minutes) parts.push(`${minutes}m`);
  if (secs || parts.length === 0) parts.push(`${secs}s`);
  return parts.join(' ');
}

function externalLink(href, className) {
  const link = document.createElement('a');
  link.href = href;
  link.target = '_blank';
  link.rel = 'noreferrer';
  if (className) link.className = className;
  return link;
}

function createGameRow(game) {
  const row = document.createElement('tr');

  const numberCell = document.createElement('td');
  numberCell.className = 'game-number';
  numberCell.textContent = game.number ?? '—';

  const iconCell = document.createElement('td');
  iconCell.className = 'game-icon-cell';
  if (game.icon) {
    const iconWrapper = game.url
      ? externalLink(game.url, 'game-table-icon')
      : document.createElement('span');
    if (!game.url) iconWrapper.className = 'game-table-icon';

    const image = document.createElement('img');
    image.src = game.icon;
    image.alt = '';
    image.loading = 'lazy';
    image.width = 40;
    image.height = 40;
    iconWrapper.append(image);
    iconCell.append(iconWrapper);
  }

  const gameCell = document.createElement('td');
  gameCell.className = 'game-title-cell';
  if (game.url) {
    const link = externalLink(game.url);
    link.textContent = text(game.name);
    gameCell.append(link);
  } else {
    gameCell.textContent = text(game.name);
  }

  const consoleCell = document.createElement('td');
  consoleCell.textContent = text(game.console);

  const genreCell = document.createElement('td');
  genreCell.textContent = text(game.genre);

  const dateCell = document.createElement('td');
  dateCell.className = 'game-date-cell';
  dateCell.textContent = formatDate(game.awardDate ?? game.date);

  const timeCell = document.createElement('td');
  timeCell.className = 'game-time-cell';
  timeCell.textContent = game.playtimeSeconds != null
    ? formatDuration(game.playtimeSeconds)
    : text(game.time);

  row.append(
    numberCell,
    iconCell,
    gameCell,
    consoleCell,
    genreCell,
    dateCell,
    timeCell
  );
  return row;
}

function renderRows(target, games) {
  target.replaceChildren();

  if (!games.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 7;
    cell.className = 'games-empty';
    cell.textContent = 'Game data has not been generated yet.';
    row.append(cell);
    target.append(row);
    return;
  }

  const fragment = document.createDocumentFragment();
  games.forEach(game => fragment.append(createGameRow(game)));
  target.append(fragment);
}

function setSourceNote(data) {
  sourceNote.replaceChildren();

  if (!data.generatedAt) {
    sourceNote.textContent = 'Waiting for the first RetroAchievements API update.';
    return;
  }

  const source = document.createElement('a');
  source.href = data.source || 'https://retroachievements.org/user/berti';
  source.target = '_blank';
  source.rel = 'noreferrer';
  source.textContent = 'RetroAchievements';

  const updated = formatDate(data.generatedAt);
  sourceNote.append('Official ', source, ` API snapshot updated ${updated}.`);
}

async function loadGames() {
  const response = await fetch('mastered-games.json', { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Could not load mastered-games.json (${response.status})`);
  }

  const data = await response.json();
  const mastered = Array.isArray(data.mastered) ? data.mastered : [];
  const beaten = Array.isArray(data.beaten) ? data.beaten : [];

  renderRows(masteredBody, mastered);
  renderRows(beatenBody, beaten);

  masteredCount.textContent = `${mastered.length} ${mastered.length === 1 ? 'game' : 'games'}`;
  beatenCount.textContent = `${beaten.length} ${beaten.length === 1 ? 'game' : 'games'}`;
  gamesCount.textContent = `${mastered.length} mastered · ${beaten.length} beaten`;
  setSourceNote(data);
}

loadGames().catch(error => {
  console.error(error);
  gamesCount.textContent = 'Error loading games';
  masteredCount.textContent = '';
  beatenCount.textContent = '';
  sourceNote.textContent = 'Could not load the RetroAchievements snapshot.';
  renderRows(masteredBody, []);
  renderRows(beatenBody, []);
});
