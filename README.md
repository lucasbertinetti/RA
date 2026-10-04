# berti × RetroAchievements

Static GitHub Pages site for **berti**'s RetroAchievements projects.

- **Mastery Icons** — gallery of game icons created/worked by berti.
- **Quests** — manually curated mastery quests.
- **Mastered Games** — automatically generated Mastered and Beaten lists using the official RetroAchievements Web API.

## Mastered Games automation

The public site never receives the RetroAchievements API key. The key is used only inside GitHub Actions to generate the static `mastered-games.json` file.

### Required GitHub secret

In the repository, open **Settings → Secrets and variables → Actions → New repository secret** and create:

- Name: `RA_API_KEY`
- Value: your RetroAchievements **Web API Key**

Do **not** add the key to any source file.

### Updating the list

`.github/workflows/update-mastered-games.yml` runs automatically once per day. It can also be run manually from:

**Actions → Update mastered games → Run workflow**

The Action commits the refreshed `mastered-games.json` back to `main`. GitHub Pages then republishes the site automatically.

### What is included

The updater uses the official RetroAchievements API and includes:

- Mastered games (`mastered`)
- Beaten hardcore games that are **not** mastered (`beaten-hardcore`)
- game icon
- game title
- console
- first genre value
- award date
- total RA-tracked playtime in seconds, displayed as a readable duration on the page

`completed` (100% with at least one softcore unlock) and `beaten-softcore` are intentionally not placed in these two lists, matching the distinction between RA's Mastered/Beaten status categories.

## Code structure

```text
.github/workflows/update-mastered-games.yml  # scheduled/manual automation
scripts/ra_api.py                            # small official API client
scripts/update_mastered_games.py             # transforms API data into site JSON
mastered-games.json                          # generated static snapshot
mastered-games.js                            # table rendering/formatting
mastered-games.html                          # Mastered Games page
quests.json / quests.js                      # quest data/page logic
icons.json / script.js                       # icon gallery data/page logic
style.css                                    # shared site styles
assets/                                      # local mastery-icon images
```

The updater caches game detail fields already present in `mastered-games.json`. After the first run, it normally needs only one completion-progress request plus detail requests for newly beaten/mastered games or games whose award status changed.
