# Beaten Games Log (schema v2)

New per-game fields: `beatenDate` (ISO 8601), `masteryDate` (ISO 8601), `timeToBeat` (human-readable text, e.g. `12h 30m`), `beatenCondition` (text), `badge_url` (URL). Edit the last three manually as needed. The updater preserves manual values.

**Important:** the RA `API_GetUserCompletionProgress` API exposes `HighestAwardDate`, which for mastered sets is the mastery date, **not** the date first beaten. Therefore the 98 mastered games have `beatenDate: null` unless specifically verified/entered. Their original award timestamps are preserved in `masteryDate`. The 143 beaten-only games inherit their verified beaten award date. The site sorts dated games first (most recent to oldest); games with unknown beaten date appear last, alphabetically. Full chronological ordering requires entering those dates.

The site includes `beaten-games-list.html` and a placeholder `beaten-games-wall.html`. Both are linked from the main navigation.
