# berti × RetroAchievements — Mastery Icons

A GitHub Pages site containing only the **Mastery Icons** gallery (`index.html`, `script.js`, `icons.json`, `assets/`, and `style.css`).

The previous Quests, Mastered Games, Statistics, and Franchises / Series sections are archived under [`legacy/`](legacy/) and are not linked on the active site.

## Unified beaten/mastered game log

[`games-log.json`](games-log.json) tracks each base game once. `beaten: true` includes mastered games; `mastered: true` identifies mastery. Subsets are excluded. Metadata includes console, developer, publisher, genre, release date (US preferred when regional dates are exposed), and franchise where known. Unknown values are `null` rather than speculative.

The uploaded October 9 snapshot provides 243 awards, of which two are explicitly tagged subsets, yielding **241** base games. The initially generated JSON uses the available local data and carries `dataStatus: partial-cache-awaiting-api-refresh`. An Action run will query the latest RetroAchievements profile and enrich metadata. Counts may change as new awards are earned.

### Setup and update

Keep the existing **`RA_API_KEY`** GitHub Actions secret (Settings → Secrets and variables → Actions). Never commit it. `.github/workflows/update-mastered-games.yml` is scheduled daily and can be triggered manually under Actions → Update RetroAchievements data → Run workflow. The Action writes only `games-log.json` and commits any changes.

### Game badge links

Every game has a `badge_url` field, initially `null`. Manually paste the complete (public) image URL to display its RetroAchievements badge in future UI features. Example:

```json
"badge_url": "https://media.retroachievements.org/Images/012345.png"
```

Use your game's *actual* image URL; the example is illustrative only. This field is deliberately **manual**: `scripts/update_games_log.py` carries it forward using the game's stable RA `id`, so subsequent GitHub Actions refreshes will **not erase or overwrite** the URL. A missing badge remains `null`.

Note: The other metadata fields (`developer`, `publisher`, etc.) may be refreshed from the RA API. If you later manually correct those fields, the current updater can overwrite them with API values; manual corrections to those fields require a separate preservation rule.
