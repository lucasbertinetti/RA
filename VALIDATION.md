# Games log validation (15 October 2026)

The archived data used to initialize `games-log.json` is dated 9 October 2026.
The public `berti` profile was checked on 15 October 2026 and displayed:
- **241** total beaten games (**239 retail**);
- **100** mastered awards and **143** beaten awards in its progress status breakdown.

In the archived completion data, **243** completion awards were recorded: 100 mastered and 143 beaten. Two mastered awards belong to explicitly titled subsets:
- Aero Fighters [Subset - Multiplayer] (game ID 17953)
- Dungeons & Dragons Collection [Subset - Multiplayer] (game ID 28268)

Excluding those gives **241 unique base games**, **98** mastered base games and **143** beaten-only base games. This matches the public profile's 241 beaten total; it does not independently establish that all 241 game IDs are unchanged since the archive. An authenticated API refresh is required to verify the latest exact roster.

Metadata in the initial cached JSON: 241/241 developer missing; 241/241 publisher missing; 29/241 genre missing; 131/241 release date missing; 131/241 franchise missing. Dates derived from the curated franchise source have no region guarantee. `null` fields were kept rather than guessed.

The API key is intentionally not present in the ZIP. The updated GitHub Actions workflow invokes `scripts/update_games_log.py` using `secrets.RA_API_KEY`, fetches the current completion roster, and queries `API_GetGameExtended` to populate/refresh metadata. The updater now revisits records with incomplete metadata instead of permanently marking them as checked. The resulting JSON includes a `validation` section tracking missing fields and subsets. The RetroAchievements `Released` date is the **earliest** game release; it does not identify the American date. Explicit region fields take precedence if ever supplied; unknown-region dates remain labeled `null`.

To run in GitHub: Actions → Update RetroAchievements data → Run workflow. After completion inspect `games-log.json` → `validation.missingMetadata` and `total`. The franchise field is derived from the manually curated legacy franchise roster; games not listed there may remain `null`.

API source: https://api-docs.retroachievements.org/v1/get-game-extended.html
Profile: https://retroachievements.org/user/berti
