# RetroAchievements Quests update

Files in this package:

- `index.html` — current gallery page with the new top navigation.
- `style.css` — shared styling for the gallery and quest page.
- `quests.html` — new Quests page.
- `quests.js` — renders Active/Finished quests, progress and summary values.
- `quests.json` — quest data converted from `Berti _ RetroAchievements.xlsx`.

Keep your existing `script.js`, `icons.json`, and `assets/` folder unchanged.

## Updating progress

Edit only `quests.json`.

Change:

```json
"mastered": false
```

to:

```json
"mastered": true
```

A quest is automatically moved from **Active Quests** to **Finished Quests** when every game in that quest has `mastered: true`.

Dates use ISO format:

```json
"startDate": "2026-07-24",
"endDate": null
```

When a quest is completed, enter the end date manually, for example:

```json
"endDate": "2026-10-03"
```

Optional game links are supported. Add `"url"` to a game and its row will become clickable:

```json
{
  "name": "Mega Man",
  "platform": "NES",
  "mastered": true,
  "url": "https://retroachievements.org/game/..."
}
```


## RetroAchievements links and game icons

Each matched game now has `raId`, `url`, and `icon` fields. The quest page shows the official RetroAchievements game icon in a compact strip below the quest header; clicking either the icon or the game row opens the matching RetroAchievements page in a new tab. Completed games have a green-accented icon, while unfinished games are slightly dimmed.

`Aero Fighters 2` is matched to the Neo Geo CD (NGCD) release on RetroAchievements: https://retroachievements.org/game/23838.
