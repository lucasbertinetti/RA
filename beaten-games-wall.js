'use strict';

const board = document.querySelector('#beatenWall');
const count = document.querySelector('#gamesCount');
const grouping = document.querySelector('#wallGrouping');
const tooltip = document.querySelector('#wallTooltip');
const tooltipName = document.querySelector('#wallTooltipName');
const tooltipDetails = document.querySelector('#wallTooltipDetails');
const dialog = document.querySelector('#wallDialog');
const dialogImage = document.querySelector('#wallDialogImage');
const dialogName = document.querySelector('#wallDialogName');
const dialogDetails = document.querySelector('#wallDialogDetails');
const dialogLink = document.querySelector('#wallDialogLink');
const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });

function label(value, fallback = 'Unknown') {
  return value == null || !String(value).trim() ? fallback : String(value).trim();
}

function genreOf(game) {
  // Normalize spelling variants already present in the games log.
  const genre = label(game.genre, 'Unknown Genre');
  if (/^beat\s*'?\s*em up$/i.test(genre)) return "Beat 'em Up";
  if (/^shoot\s*'?\s*em up$/i.test(genre)) return "Shoot 'em Up";
  return genre;
}

function timestamp(game) {
  const value = game.releaseDate;
  if (!value) return Number.POSITIVE_INFINITY;
  const time = Date.parse(String(value));
  return Number.isFinite(time) ? time : Number.POSITIVE_INFINITY;
}

function alphabetic(a, b) { return collator.compare(a, b); }

function orderWithinGenre(games) {
  // Group all members of a named franchise; unassigned titles stand alone.
  // A franchise takes the place of its earliest released game, not its name.
  const families = new Map();
  games.forEach(game => {
    const franchise = game.franchise && String(game.franchise).trim();
    const key = franchise ? `franchise:${franchise.toLocaleLowerCase('en')}` : `game:${game.id}`;
    if (!families.has(key)) families.set(key, []);
    families.get(key).push(game);
  });
  const familyList = [...families.values()];
  familyList.forEach(members => members.sort((a, b) =>
    timestamp(a) - timestamp(b) || alphabetic(label(a.name), label(b.name)) || Number(a.id) - Number(b.id)
  ));
  familyList.sort((a, b) =>
    timestamp(a[0]) - timestamp(b[0]) ||
    alphabetic(label(a[0].name), label(b[0].name))
  );
  return familyList.flat();
}

function hideTooltip() {
  tooltip.classList.remove('is-visible');
  tooltip.setAttribute('aria-hidden', 'true');
}

function showTooltip(card, game) {
  tooltipName.textContent = label(game.name, `Game ${game.id}`);
  tooltipDetails.textContent = [label(game.console), game.releaseDate ? String(game.releaseDate).slice(0, 4) : null, game.franchise || null].filter(Boolean).join(' · ');
  tooltip.classList.add('is-visible');
  tooltip.setAttribute('aria-hidden', 'false');
  const bounds = card.getBoundingClientRect();
  tooltip.style.top = `${bounds.top}px`;
  tooltip.style.left = `${bounds.left + bounds.width / 2}px`;
  const tip = tooltip.getBoundingClientRect();
  const margin = 10;
  let x = bounds.left + bounds.width / 2;
  if (tip.left < margin) x += margin - tip.left;
  if (tip.right > window.innerWidth - margin) x -= tip.right - (window.innerWidth - margin);
  tooltip.style.left = `${x}px`;
}

function makeBadge(game) {
  const title = label(game.name, `Game ${game.id}`);
  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'icon-card beaten-wall-card';
  card.setAttribute('aria-label', `${title} — ${label(game.console)}`);
  const image = document.createElement('img');
  image.src = game.badge_url;
  image.alt = title;
  image.loading = 'lazy';
  image.draggable = false;
  card.append(image);
  card.addEventListener('mouseenter', () => showTooltip(card, game));
  card.addEventListener('mouseleave', hideTooltip);
  card.addEventListener('focus', () => showTooltip(card, game));
  card.addEventListener('blur', hideTooltip);
  card.addEventListener('click', () => {
    hideTooltip();
    dialogImage.src = game.badge_url;
    dialogImage.alt = title;
    dialogName.textContent = title;
    dialogDetails.textContent = [label(game.console), genreOf(game), game.franchise || null, game.releaseDate ? `Released: ${game.releaseDate}` : null].filter(Boolean).join(' · ');
    if (game.id != null) {
      dialogLink.href = `https://retroachievements.org/game/${encodeURIComponent(game.id)}`;
      dialogLink.hidden = false;
    } else dialogLink.hidden = true;
    dialog.showModal();
  });
  return card;
}

// Display franchise names as stored in the catalog; differences in case do not split a series.
function franchiseGroups(games) {
  const groups = new Map();
  const unassigned = [];
  games.forEach(game => {
    const name = game.franchise == null ? '' : String(game.franchise).trim();
    if (!name) { unassigned.push(game); return; }
    const key = name.toLocaleLowerCase('en');
    if (!groups.has(key)) groups.set(key, { name, games: [] });
    groups.get(key).games.push(game);
  });
  const series = [...groups.values()];
  series.forEach(group => group.games.sort((a, b) =>
    timestamp(a) - timestamp(b) || alphabetic(label(a.name), label(b.name)) || Number(a.id) - Number(b.id)
  ));
  series.sort((a, b) => b.games.length - a.games.length || alphabetic(a.name, b.name));
  return { series, unassigned };
}

function makeSectionHeading(name, amount, headingClass) {
  const heading = document.createElement('h2');
  heading.className = headingClass;
  heading.textContent = name;
  const number = document.createElement('span');
  number.className = 'beaten-wall-genre-count';
  number.textContent = ` ${amount}`;
  heading.append(number);
  return heading;
}

function renderFranchises(games, fragment) {
  const { series, unassigned } = franchiseGroups(games);
  const layout = document.createElement('div');
  layout.className = 'beaten-wall-franchise-layout';
  layout.setAttribute('aria-label', 'Franchises and series, largest to smallest');
  const lanes = Array.from({ length: 3 }, () => {
    const lane = document.createElement('div');
    lane.className = 'beaten-wall-franchise-lane';
    layout.append(lane);
    return { element: lane, height: 0 };
  });
  series.forEach(group => {
    // Greedy shortest-column distribution keeps uneven groups from leaving empty rows.
    const lane = lanes.reduce((best, current) => current.height < best.height ? current : best);
    const section = document.createElement('section');
    section.className = 'beaten-wall-franchise';
    section.append(makeSectionHeading(group.name, group.games.length, 'beaten-wall-genre-heading'));
    const grid = document.createElement('div');
    grid.className = 'beaten-wall-grid beaten-wall-five-grid';
    grid.setAttribute('aria-label', `${group.name} games`);
    group.games.forEach(game => grid.append(makeBadge(game)));
    section.append(grid);
    lane.element.append(section);
    lane.height += Math.ceil(group.games.length / 5) + 0.4;
  });
  fragment.append(layout);

  if (unassigned.length) {
    const section = document.createElement('section');
    section.className = 'beaten-wall-unassigned';
    section.append(makeSectionHeading('No Franchise/Series', unassigned.length, 'beaten-wall-genre-heading'));
    const consoles = new Map();
    unassigned.forEach(game => {
      const consoleName = label(game.console, 'Unknown Console');
      if (!consoles.has(consoleName)) consoles.set(consoleName, []);
      consoles.get(consoleName).push(game);
    });
    [...consoles.keys()].sort(alphabetic).forEach(consoleName => {
      const block = document.createElement('section');
      block.className = 'beaten-wall-console';
      block.append(makeSectionHeading(consoleName, consoles.get(consoleName).length, 'beaten-wall-console-heading'));
      const grid = document.createElement('div');
      grid.className = 'beaten-wall-grid';
      grid.setAttribute('aria-label', `${consoleName} games without a franchise`);
      consoles.get(consoleName).sort((a, b) => timestamp(a) - timestamp(b) || alphabetic(label(a.name), label(b.name)));
      consoles.get(consoleName).forEach(game => grid.append(makeBadge(game)));
      block.append(grid);
      section.append(block);
    });
    fragment.append(section);
  }
}

function render(games) {
  const byGenre = new Map();
  games.forEach(game => {
    const genre = genreOf(game);
    if (!byGenre.has(genre)) byGenre.set(genre, []);
    byGenre.get(genre).push(game);
  });
  const genres = [...byGenre.keys()].sort((a, b) =>
    a === 'Unknown Genre' ? 1 : b === 'Unknown Genre' ? -1 : alphabetic(a, b)
  );
  const fragment = document.createDocumentFragment();
  // Genre and None retain their original ordering and layout.
  if (grouping.value === 'franchise') {
    renderFranchises(games, fragment);
  } else if (grouping.value === 'none') {
    const grid = document.createElement('div');
    grid.className = 'beaten-wall-grid';
    grid.setAttribute('aria-label', 'All beaten games');
    genres.forEach(genre => {
      orderWithinGenre(byGenre.get(genre)).forEach(game => grid.append(makeBadge(game)));
    });
    fragment.append(grid);
  } else {
  genres.forEach(genre => {
    const section = document.createElement('section');
    section.className = 'beaten-wall-genre';
    const heading = document.createElement('h2');
    heading.className = 'beaten-wall-genre-heading';
    heading.append(document.createTextNode(genre));
    const number = document.createElement('span');
    number.className = 'beaten-wall-genre-count';
    number.textContent = ` ${byGenre.get(genre).length}`;
    heading.append(number);
    const grid = document.createElement('div');
    grid.className = 'beaten-wall-grid';
    grid.setAttribute('aria-label', `${genre} games`);
    orderWithinGenre(byGenre.get(genre)).forEach(game => grid.append(makeBadge(game)));
    section.append(heading, grid);
    fragment.append(section);
  });
  }
  board.replaceChildren(fragment);
  count.textContent = `${games.length} beaten games`;
}

async function load() {
  try {
    const response = await fetch('games-log.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Could not load games-log.json (${response.status})`);
    const data = await response.json();
    const games = (Array.isArray(data) ? data : data.games || []).filter(game => game.beaten === true);
    render(games);
    grouping.addEventListener('change', () => render(games));
  } catch (error) {
    console.error(error);
    count.textContent = 'Unable to load games';
    board.textContent = 'The games could not be loaded. Check games-log.json.';
  }
}

window.addEventListener('scroll', hideTooltip, true);
window.addEventListener('resize', hideTooltip);
dialog.querySelector('.close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
load();
