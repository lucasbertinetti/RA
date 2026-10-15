# berti × RetroAchievements — personal games catalog

Static GitHub Pages website with three tabs: **Mastery Icons**, **Beaten Games List**, and **Beaten Games Wall** (placeholder). The previous site sections are archived under [`legacy/`](legacy/).

## Manual updates only

**There are no GitHub Actions workflows, automatic RetroAchievements API queries, scheduled jobs, or updater scripts in the active project.** Neither the site nor `games-log.json` is automatically modified.

Edit [`games-log.json`](games-log.json) yourself and commit/push it to GitHub. **Beaten Games List** reads this same JSON in the browser when the page is opened or reloaded, sorts by `beatenDate` from newest to oldest, and recalculates numbering. Missing dates are listed last. Thus changing dates or other fields requires no HTML edits, but you do need to publish the JSON change and reload the page. The website does not make write requests or update the source JSON.

The Mastery Icons gallery reads the committed local [`icons.json`](icons.json); its icons and imagery are also edited manually. The **Beaten Games Wall** is reserved for future changes.

## JSON catalog

Each base game appears once; `beaten: true` includes mastered games, with `mastered: true` as an additional marker. Subsets are excluded. The snapshot contains **241 base games**. Unknown fields are `null` and can be completed by hand, including `developer`, `publisher`, `genre`, `releaseDate`, `franchise`, `badge_url`, `timeToBeat`, `beatenCondition`, and `beatenDate`. Manual changes are no longer overwritten by any updater.

The cached data dates from **9 October 2026**, and dates for previously mastered games have not been verified as beaten dates; read [`BEATEN-GAMES-NOTES.md`](BEATEN-GAMES-NOTES.md) and [`VALIDATION.md`](VALIDATION.md) for these limitations.

There is no requirement to keep the old `RA_API_KEY` GitHub secret for this version. If the repository formerly had that secret, you may delete it in GitHub Settings → Secrets and variables → Actions. GitHub Pages still publishes the site as configured under Settings → Pages.
