"use strict";
const tbody = document.querySelector('#beatenListBody');
const count = document.querySelector('#gamesCount');
const notice = document.querySelector('#beatenNotice');
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
async function load() {
  try {
    const response = await fetch('games-log.json', {cache:'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const games = (data.games || []).filter(g => g.beaten || g.mastered);
    // No fabricated beaten dates for mastered games: undated games remain at the end.
    games.sort((a,b) => {
      const ta = a.beatenDate ? Date.parse(a.beatenDate) : -Infinity;
      const tb = b.beatenDate ? Date.parse(b.beatenDate) : -Infinity;
      return (Number.isNaN(tb)?-Infinity:tb)-(Number.isNaN(ta)?-Infinity:ta) || a.name.localeCompare(b.name);
    });
    tbody.replaceChildren();
    games.forEach((game,index) => {
      const tr = document.createElement('tr');
      cell(tr, games.length-index, 'game-number');
      const title = document.createElement('td');
      title.className = 'game-title-cell';
      tr.append(title);
      const a = document.createElement('a');
      a.href = `https://retroachievements.org/game/${encodeURIComponent(game.id)}`;
      a.target = '_blank'; a.rel='noopener noreferrer';
      a.textContent=game.name || `Game ${game.id}`;
      title.append(a);
      for (const field of ['console','genre','developer','publisher','timeToBeat']) cell(tr,game[field]);
      cell(tr,formatDate(game.beatenDate),'game-date-cell');
      cell(tr,game.beatenCondition);
      tbody.append(tr);
    });
    count.textContent = `${games.length} games beaten`;
    const missing = games.filter(g => !g.beatenDate).length;
    notice.textContent = `${missing} games have no verified beaten date; these appear after dated games. Mastery dates are never used as substitutes. Data: RetroAchievements / games-log.json.`;
  } catch(err) {
    tbody.replaceChildren();const tr=document.createElement('tr');cell(tr,`Could not load games-log.json: ${err.message}`).colSpan=9;tbody.append(tr);count.textContent='Unavailable';
  }
}
load();
