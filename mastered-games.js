const masteredBody = document.querySelector('#masteredGamesBody');
const beatenBody = document.querySelector('#beatenGamesBody');
const masteredCount = document.querySelector('#masteredCount');
const beatenCount = document.querySelector('#beatenCount');
const gamesCount = document.querySelector('#gamesCount');
const sourceNote = document.querySelector('#gamesSourceNote');

function escapeText(value, fallback = '—') {
  const text = String(value ?? '').trim();
  return text || fallback;
}

function formatSnapshotDate(value) {
  if (!value) return '';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  return new Intl.DateTimeFormat('en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(date);
}

function createGameRow(game) {
  const row = document.createElement('tr');

  const numberCell = document.createElement('td');
  numberCell.className = 'game-number';
  numberCell.textContent = game.number ?? '—';

  const iconCell = document.createElement('td');
  iconCell.className = 'game-icon-cell';

  if (game.icon) {
    const iconLink = document.createElement(game.url ? 'a' : 'span');
    iconLink.className = 'game-table-icon';

    if (game.url) {
      iconLink.href = game.url;
      iconLink.target = '_blank';
      iconLink.rel = 'noreferrer';
    }

    const image = document.createElement('img');
    image.src = game.icon;
    image.alt = '';
    image.loading = 'lazy';
    image.width = 40;
    image.height = 40;
    iconLink.append(image);
    iconCell.append(iconLink);
  }

  const gameCell = document.createElement('td');
  gameCell.className = 'game-title-cell';

  if (game.url) {
    const link = document.createElement('a');
    link.href = game.url;
    link.target = '_blank';
    link.rel = 'noreferrer';
    link.textContent = escapeText(game.name);
    gameCell.append(link);
  } else {
    gameCell.textContent = escapeText(game.name);
  }

  const consoleCell = document.createElement('td');
  consoleCell.textContent = escapeText(game.console);

  const genreCell = document.createElement('td');
  genreCell.textContent = escapeText(game.genre);

  const dateCell = document.createElement('td');
  dateCell.className = 'game-date-cell';
  dateCell.textContent = escapeText(game.date);

  const timeCell = document.createElement('td');
  timeCell.className = 'game-time-cell';
  timeCell.textContent = escapeText(game.time);

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

fetch('mastered-games.json?v=1', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) {
      throw new Error(`Could not load mastered-games.json (${response.status})`);
    }
    return response.json();
  })
  .then(data => {
    const mastered = Array.isArray(data.mastered) ? data.mastered : [];
    const beaten = Array.isArray(data.beaten) ? data.beaten : [];

    renderRows(masteredBody, mastered);
    renderRows(beatenBody, beaten);

    masteredCount.textContent = `${mastered.length} games`;
    beatenCount.textContent = `${beaten.length} games`;
    gamesCount.textContent = `${mastered.length} mastered · ${beaten.length} beaten`;

    const snapshot = formatSnapshotDate(data.generatedAt);
    sourceNote.textContent = snapshot
      ? `RetroAchievements snapshot updated ${snapshot}.`
      : 'RetroAchievements data will be populated automatically after the repository update runs.';
  })
  .catch(error => {
    console.error(error);
    gamesCount.textContent = 'Error loading games';
    masteredCount.textContent = '';
    beatenCount.textContent = '';
    sourceNote.textContent = 'Could not load the RetroAchievements game snapshot.';
    renderRows(masteredBody, []);
    renderRows(beatenBody, []);
  });
