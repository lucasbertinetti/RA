# Beaten Games Log (schema v2)

Per-game fields include `beatenDate` (ISO 8601), `masteryDate` (ISO 8601), `timeToBeat` (human-readable text, e.g. `12h 30m`), `beatenCondition` (text), and `badge_url` (public image URL). All can be edited manually in `games-log.json`. **No bot or scheduled sync updates them.**

The archived RetroAchievements completion response provided `HighestAwardDate`, which for mastered games is the mastery date rather than the date first beaten. Consequently the 98 mastered base games have `beatenDate: null` pending manual verification. The 143 beaten-only games have their beaten dates. The Beaten Games List sorts available beaten dates newest first, then undated games alphabetically; numbering recalculates at page load. Changes take effect after publishing the edited JSON and reloading the page.

The Beaten Games Wall is a placeholder awaiting future layout requirements.
