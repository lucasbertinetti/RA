"use strict";
const tbody = document.querySelector('#beatenListBody');
const count = document.querySelector('#gamesCount');
const notice = document.querySelector('#beatenNotice');
const headers = [...document.querySelectorAll('.beaten-log-table th[data-sort]')];
const collator = new Intl.Collator('en', {numeric:true, sensitivity:'base'});
let games = [];
let sortKey = 'beatenDate';
let sortDirection = 'desc';

function cell(row, value, className = '') {
  const td = document.createElement('td');
  if (className) td.className = className;
  td.textContent = value == null || value === '' ? '—' : String(value);
  row.append(td);
  return td;
}
function formatDate(input) {
  if (!input) return '—';
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return String(input);
  return new Intl.DateTimeFormat('en-US', {year:'numeric', month:'short', day:'2-digit', timeZone:'UTC'}).format(date);
}
function timeMinutes(value) {
  if (value == null || String(value).trim() === '') return null;
  const text = String(value).trim().toLowerCase();
  const hours = /([\d.,]+)\s*(?:h|hours?)/.exec(text);
  const minutes = /([\d.,]+)\s*(?:m|min|minutes?)/.exec(text);
  const seconds = /([\d.,]+)\s*(?:s|sec|seconds?)/.exec(text);
  const numeric = s => Number(s.replace(',', '.'));
  if (hours || minutes || seconds) return (hours ? numeric(hours[1])*60 : 0) + (minutes ? numeric(minutes[1]) : 0) + (seconds ? numeric(seconds[1])/60 : 0);
  if (/^\d+(?:[.,]\d+)?$/.test(text)) return numeric(text);
  return null;
}
function sortValue(game, key) {
  if (key === 'number') return game._originalNumber;
  if (key === 'timeToBeat') return timeMinutes(game.timeToBeat);
  if (key === 'beatenDate') {
    const date = game.beatenDate ? Date.parse(game.beatenDate) : NaN;
    return Number.isFinite(date) ? date : null;
  }
  return game[key] == null || String(game[key]).trim() === '' ? null : String(game[key]).trim();
}
function sortedGames() {
  const direction = sortDirection === 'asc' ? 1 : -1;
  return [...games].sort((a,b) => {
    const x = sortValue(a, sortKey);
    const y = sortValue(b, sortKey);
    // Unknown values are always at the end, in both directions.
    if (x == null && y != null) return 1;
    if (y == null && x != null) return -1;
    let difference = 0;
    if (x != null && y != null) difference = typeof x === 'number' && typeof y === 'number' ? x-y : collator.compare(x,y);
    return difference * direction || collator.compare(a.name || '', b.name || '') || a._originalNumber-b._originalNumber;
  });
}
function render() {
  const ordered = sortedGames();
  const fragment = document.createDocumentFragment();
  ordered.forEach((game,index) => {
    const tr = document.createElement('tr');
    cell(tr, ordered.length-index, 'game-number');
    const title = document.createElement('td');
    title.className = 'game-title-cell';
    tr.append(title);
    const a = document.createElement('a');
    a.href = `https://retroachievements.org/game/${encodeURIComponent(game.id)}`;
    a.target = '_blank'; a.rel='noopener noreferrer';
    a.textContent = game.name || `Game ${game.id}`;
    title.append(a);
    for (const field of ['console','genre','developer','publisher','timeToBeat']) cell(tr,game[field]);
    cell(tr,formatDate(game.beatenDate),'game-date-cell');
    fragment.append(tr);
  });
  tbody.replaceChildren(fragment);
  headers.forEach(header => {
    const active = header.dataset.sort === sortKey;
    header.setAttribute('aria-sort', active ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none');
    const arrow = header.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = active ? (sortDirection === 'asc' ? '▲' : '▼') : '↕';
  });
}
headers.forEach(header => {
  header.querySelector('button').addEventListener('click', () => {
    if (sortKey === header.dataset.sort) sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    else {
      sortKey = header.dataset.sort;
      sortDirection = sortKey === 'beatenDate' || sortKey === 'number' ? 'desc' : 'asc';
    }
    render();
  });
});
async function load() {
  try {
    const response = await fetch('games-log.json', {cache:'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    games = (data.games || []).filter(g => g.beaten || g.mastered).map((g,i) => ({...g,_originalNumber:i}));
    render();
    count.textContent = `${games.length} games beaten`;
    const missing = games.filter(g => !g.beatenDate).length;
    notice.textContent = `${missing} games have no verified beaten date. Missing values appear last when sorting. Mastery dates are never used as substitutes. Data: RetroAchievements / games-log.json.`;
  } catch(err) {
    tbody.replaceChildren();const tr=document.createElement('tr');cell(tr,`Could not load games-log.json: ${err.message}`).colSpan=8;tbody.append(tr);count.textContent='Unavailable';
  }
}
load();
