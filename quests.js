const activeContainer = document.querySelector('#activeQuests');
const finishedContainer = document.querySelector('#finishedQuests');

const DATE_FORMATTER = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric'
});

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : DATE_FORMATTER.format(date);
}

function questStats(quest) {
  const total = quest.games.length;
  const mastered = quest.games.filter(game => game.mastered).length;
  const percent = total === 0 ? 0 : Math.round((mastered / total) * 100);
  const finished = total > 0 && mastered === total;

  return { total, mastered, percent, finished };
}

function gameRow(game) {
  const row = document.createElement(game.url ? 'a' : 'div');
  row.className = `quest-game${game.mastered ? ' is-mastered' : ''}`;

  if (game.url) {
    row.href = game.url;
    row.target = '_blank';
    row.rel = 'noreferrer';
    row.title = 'Open on RetroAchievements';
  }

  const state = document.createElement('span');
  state.className = 'game-state';
  state.setAttribute('aria-label', game.mastered ? 'Mastered' : 'Not mastered');
  state.textContent = game.mastered ? '✓' : '';

  const name = document.createElement('span');
  name.className = 'game-name';
  name.textContent = game.name;

  const platform = document.createElement('span');
  platform.className = 'platform-badge';
  platform.textContent = game.platform || '—';

  row.append(state, name, platform);
  return row;
}


function questIconStrip(quest) {
  const strip = document.createElement('div');
  strip.className = 'quest-icon-strip';
  strip.setAttribute('aria-label', `${quest.title} game icons`);

  quest.games.forEach(game => {
    const item = document.createElement(game.url ? 'a' : 'span');
    item.className = `quest-icon-item${game.mastered ? ' is-mastered' : ''}${game.url ? '' : ' is-unlinked'}`;

    if (game.url) {
      item.href = game.url;
      item.target = '_blank';
      item.rel = 'noreferrer';
      item.title = `${game.name} (${game.platform}) — Open on RetroAchievements`;
    } else {
      item.title = `${game.name} (${game.platform}) — RetroAchievements link pending`;
    }

    if (game.icon) {
      const img = document.createElement('img');
      img.className = 'quest-game-icon';
      img.src = game.icon;
      img.alt = '';
      img.width = 40;
      img.height = 40;
      img.loading = 'lazy';
      img.decoding = 'async';
      item.append(img);
    } else {
      const fallback = document.createElement('span');
      fallback.className = 'quest-game-icon-fallback';
      fallback.textContent = '?';
      item.append(fallback);
    }

    strip.append(item);
  });

  return strip;
}

function questCard(quest) {
  const stats = questStats(quest);

  const article = document.createElement('article');
  article.className = `quest-card${stats.finished ? ' is-finished' : ''}`;

  const header = document.createElement('header');
  header.className = 'quest-card-header';

  const titleBlock = document.createElement('div');
  titleBlock.className = 'quest-title-block';

  const title = document.createElement('h3');
  title.textContent = quest.title;

  const dates = document.createElement('p');
  dates.className = 'quest-dates';
  dates.innerHTML = `
    <span><b>Start</b> ${formatDate(quest.startDate)}</span>
    <span class="date-divider">•</span>
    <span><b>End</b> ${formatDate(quest.endDate)}</span>
  `;

  titleBlock.append(title, dates);

  const percent = document.createElement('div');
  percent.className = 'quest-percent';
  percent.innerHTML = `<strong>${stats.percent}%</strong><span>${stats.mastered}/${stats.total}</span>`;

  header.append(titleBlock, percent);

  const iconStrip = questIconStrip(quest);

  const games = document.createElement('div');
  games.className = 'quest-games';
  quest.games.forEach(game => games.append(gameRow(game)));

  const footer = document.createElement('footer');
  footer.className = 'quest-card-footer';

  const progress = document.createElement('div');
  progress.className = 'progress-track';
  progress.setAttribute('role', 'progressbar');
  progress.setAttribute('aria-valuemin', '0');
  progress.setAttribute('aria-valuemax', '100');
  progress.setAttribute('aria-valuenow', String(stats.percent));
  progress.setAttribute('aria-label', `${stats.mastered} of ${stats.total} games mastered`);

  const fill = document.createElement('span');
  fill.className = 'progress-fill';
  fill.style.width = `${stats.percent}%`;
  progress.append(fill);

  const caption = document.createElement('div');
  caption.className = 'progress-caption';
  caption.innerHTML = stats.finished
    ? `<span class="completed-mark">★ Quest completed</span><span>${stats.total} games mastered</span>`
    : `<span>${stats.mastered} of ${stats.total} mastered</span><span>${stats.total - stats.mastered} remaining</span>`;

  footer.append(progress, caption);
  article.append(header, iconStrip, games, footer);

  return article;
}

function renderQuests(quests) {
  const active = [];
  const finished = [];

  let masteredGames = 0;
  let totalGames = 0;

  quests.forEach(quest => {
    const stats = questStats(quest);
    masteredGames += stats.mastered;
    totalGames += stats.total;

    if (stats.finished) finished.push(quest);
    else active.push(quest);
  });

  activeContainer.replaceChildren(...active.map(questCard));
  finishedContainer.replaceChildren(...finished.map(questCard));

  document.querySelector('#activeCount').textContent =
    `${active.length} ${active.length === 1 ? 'quest' : 'quests'}`;
  document.querySelector('#finishedCount').textContent =
    `${finished.length} ${finished.length === 1 ? 'quest' : 'quests'}`;

  document.querySelector('#activeQuestTotal').textContent = active.length;
  document.querySelector('#finishedQuestTotal').textContent = finished.length;
  document.querySelector('#masteredGameTotal').textContent = `${masteredGames}/${totalGames}`;
  document.querySelector('#questCount').textContent = `${quests.length} quests`;
}

fetch('quests.json?v=3', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) {
      throw new Error(`Could not load quests.json (${response.status})`);
    }
    return response.json();
  })
  .then(renderQuests)
  .catch(error => {
    console.error(error);
    activeContainer.innerHTML =
      '<p class="quest-error">Could not load quest data.</p>';
    document.querySelector('#questCount').textContent = 'Error loading quests';
  });
