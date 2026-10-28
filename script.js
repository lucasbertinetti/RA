// Ordered PNG filename numbers for each gallery (not icons.json positional IDs).
const PIXEL_ART_IDS = [4, 9, 10, 13, 14, 15, 16, 17, 18, 19, 20, 37, 38, 41, 45, 46, 47, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 68, 73, 74, 95, 96, 76, 77, 78, 79, 80, 81, 82, 83, 85, 88, 90, 91, 92, 93, 97, 98, 99, 100, 101, 102, 103];
const GAME_MATERIAL_IDS = [1, 2, 3, 5, 6, 7, 8, 11, 12, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 39, 40, 42, 43, 44, 48, 49, 50, 51, 52, 65, 69, 70, 71, 72, 94, 75, 84, 86, 87, 89];
const galleries = [
  { ids: PIXEL_ART_IDS, wall: document.querySelector('#pixelWall'), count: document.querySelector('#pixelCount') },
  { ids: GAME_MATERIAL_IDS, wall: document.querySelector('#gameWall'), count: document.querySelector('#gameCount') },
];

const dialog = document.querySelector('#iconDialog');
const closeButton = dialog.querySelector('.close');
const dialogImage = document.querySelector('#dialogImage');
const dialogGame = document.querySelector('#dialogGame');
const dialogConsole = document.querySelector('#dialogConsole');
const dialogLink = document.querySelector('#dialogLink');

const hoverTooltip = document.querySelector('#hoverTooltip');
const tooltipGame = document.querySelector('#tooltipGame');
const tooltipConsole = document.querySelector('#tooltipConsole');

const COLUMN_COUNT = 15;

function displayName(item) {
  return item.identified && item.game
    ? item.game
    : `Icon #${String(item.id).padStart(2, '0')}`;
}

function consoleName(item) {
  return item.identified && item.console
    ? item.console
    : 'Game identification pending';
}

function positionTooltip(card) {
  const rect = card.getBoundingClientRect();

  const centerX = rect.left + rect.width / 2;
  const topY = rect.top;

  hoverTooltip.style.left = `${centerX}px`;
  hoverTooltip.style.top = `${topY}px`;

  const tooltipRect = hoverTooltip.getBoundingClientRect();
  const margin = 10;

  let correctedCenterX = centerX;

  if (tooltipRect.left < margin) {
    correctedCenterX += margin - tooltipRect.left;
  }

  if (tooltipRect.right > window.innerWidth - margin) {
    correctedCenterX -= tooltipRect.right - (window.innerWidth - margin);
  }

  hoverTooltip.style.left = `${correctedCenterX}px`;
}

function showTooltip(card, item) {
  tooltipGame.textContent = displayName(item);
  tooltipConsole.textContent = consoleName(item);

  hoverTooltip.classList.add('is-visible');
  hoverTooltip.setAttribute('aria-hidden', 'false');

  positionTooltip(card);
}

function hideTooltip() {
  hoverTooltip.classList.remove('is-visible');
  hoverTooltip.setAttribute('aria-hidden', 'true');
}

fetch('icons.json?v=4', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) {
      throw new Error(`Could not load icons.json (${response.status})`);
    }

    return response.json();
  })
  .then(items => {
    document.querySelector('#count').textContent = `${items.length} icons`;

    // Filename is authoritative: id/row/col represent the old wall position.
    const itemsByFileNumber = new Map();
    items.forEach(item => {
      const match = /(?:^|\/)icon-(\d{3})\.png$/i.exec(item.file || '');
      if (match) {
        itemsByFileNumber.set(Number(match[1]), item);
      }
    });

    galleries.forEach(gallery => {
      gallery.count.textContent = `(${gallery.ids.length})`;
      gallery.ids.forEach(id => {
        const item = itemsByFileNumber.get(id);
        if (!item) {
          console.warn(`icon-${String(id).padStart(3, '0')}.png is listed in a gallery but missing from icons.json`);
          return;
        }

        const card = document.createElement('button');
        card.className = 'icon-card';
        card.type = 'button';

      card.setAttribute(
        'aria-label',
        `${displayName(item)} — ${consoleName(item)}`
      );

      const img = document.createElement('img');
      img.src = item.file;
      img.alt = displayName(item);
      img.loading = 'lazy';
      img.draggable = false;

      card.append(img);

      card.addEventListener('mouseenter', () => {
        showTooltip(card, item);
      });

      card.addEventListener('mouseleave', () => {
        hideTooltip();
      });

      card.addEventListener('focus', () => {
        showTooltip(card, item);
      });

      card.addEventListener('blur', () => {
        hideTooltip();
      });

      card.addEventListener('click', () => {
        hideTooltip();

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

      gallery.wall.append(card);
      });
    });
  })
  .catch(error => {
    console.error(error);
    document.querySelector('#count').textContent = 'Error loading icons';
  });

window.addEventListener('scroll', hideTooltip, true);
window.addEventListener('resize', hideTooltip);

closeButton.addEventListener('click', () => dialog.close());

dialog.addEventListener('click', event => {
  if (event.target === dialog) {
    dialog.close();
  }
});
