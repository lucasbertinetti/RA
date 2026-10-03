
const wall = document.querySelector('#wall');
const dialog = document.querySelector('#iconDialog');
const closeButton = dialog.querySelector('.close');
const dialogImage = document.querySelector('#dialogImage');
const dialogGame = document.querySelector('#dialogGame');
const dialogConsole = document.querySelector('#dialogConsole');
const dialogLink = document.querySelector('#dialogLink');

function displayName(item) {
  return item.identified && item.game ? item.game : `Icon #${String(item.id).padStart(2, '0')}`;
}

function consoleName(item) {
  return item.identified && item.console ? item.console : 'Game identification pending';
}

fetch('icons.json')
  .then(r => r.json())
  .then(items => {
    document.querySelector('#count').textContent = `${items.length} icons`;
    items.forEach(item => {
      const card = document.createElement('button');
      card.className = 'icon-card';
      card.style.gridColumn = item.col;
      card.style.gridRow = item.row;
      card.setAttribute('aria-label', `${displayName(item)} — ${consoleName(item)}`);

      const img = document.createElement('img');
      img.src = item.file;
      img.alt = displayName(item);
      img.loading = 'lazy';
      img.draggable = false;

      const tooltip = document.createElement('span');
      tooltip.className = 'tooltip';
      tooltip.innerHTML = `<strong>${displayName(item)}</strong><span>${consoleName(item)}</span>`;

      card.append(img, tooltip);
      card.addEventListener('click', () => {
        dialogImage.src = item.file;
        dialogImage.alt = displayName(item);
        dialogGame.textContent = displayName(item);
        dialogConsole.textContent = consoleName(item);
        if (item.url) {
          dialogLink.href = item.url;
          dialogLink.hidden = false;
        } else {
          dialogLink.hidden = true;
        }
        dialog.showModal();
      });
      wall.append(card);
    });
  });

closeButton.addEventListener('click', () => dialog.close());
dialog.addEventListener('click', (event) => {
  if (event.target === dialog) dialog.close();
});
