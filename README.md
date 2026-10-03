# berti — Mastery Icon Gallery

Static GitHub Pages-ready gallery generated from the PSD.

- `index.html`: page
- `style.css`: RetroAchievements-inspired dark/gold mural styling
- `script.js`: hover/click behavior
- `icons.json`: editable metadata for all 93 icons
- `assets/`: extracted 96×96 mastery icons

To identify an icon, edit its entry in `icons.json` and set:

```json
{
  "game": "Chrono Trigger",
  "console": "SNES/Super Famicom",
  "url": "https://retroachievements.org/game/...",
  "identified": true
}
```
