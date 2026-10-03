const wall = document.querySelector('#wall');

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

/*
  Reads the largest "row" value in icons.json.

  Example:
    if the badges use rows 1 through 7 -> gallery has 7 rows
    if one badge uses row 8          -> gallery has 8 rows
    if one badge later uses row 12  -> gallery has 12 rows

  No CSS edit is necessary.
*/
function getRequiredRowCount(items) {
  const validRows = items
    .map(item => Number(item.row))
    .filter(row => Number.isInteger(row) && row >= 1);

  return validRows.length > 0
    ? Math.max(...validRows)
    : 1;
}

function validatePosition(item) {
  const col = Number(item.col);
  const row = Number(item.row);

  if (!Number.isInteger(col) || col < 1 || col > COLUMN_COUNT) {
    console.warn(
      `Icon ${item.id}: invalid col "${item.col}". ` +
      `Use an integer from 1 to ${COLUMN_COUNT}.`
    );
    return false;
  }

  if (!Number.isInteger(row) || row < 1) {
    console.warn(
      `Icon ${item.id}: invalid row "${item.row}". ` +
      `Use an integer greater than or equal to 1.`
    );
    return false;
  }

  return true;
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

    /*
      AUTO-EXPANDING ROWS
      -------------------------------------------------------
      This is the key line for the new behavior.

      If the largest row in icons.json is 8, CSS receives --rows: 8.
      If it is 9, CSS receives --rows: 9, and so on.
    */
    const requiredRows = getRequiredRowCount(items);
    wall.style.setProperty('--rows', requiredRows);

    items.forEach(item => {
      if (!validatePosition(item)) {
        return;
      }

      const card = document.createElement('button');
      card.className = 'icon-card';
      card.type = 'button';

      /*
        Badge position depends ONLY on these two values in icons.json:
          "col": 1 to 15
          "row": 1, 2, 3, 4... with no fixed upper limit

        Old x/y values, if present, are ignored.
      */
      card.style.gridColumn = String(item.col);
      card.style.gridRow = String(item.row);

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

      wall.append(card);
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
