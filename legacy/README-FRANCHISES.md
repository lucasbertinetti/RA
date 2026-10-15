# Franchises / Series data

The Series page uses a hybrid updater because the official RetroAchievements Web API does not currently expose Hub membership.

## What is manual

`franchises-source.json` contains the **RA Series hubs** that are relevant to `berti`'s Mastered games. The current file was manually audited against the 100 Mastered games on **2026-10-04**.

A Series entry looks like this:

```json
{
  "id": "mega-man-classic",
  "name": "Mega Man (Classic)",
  "hubId": 2161,
  "hubUrl": "https://retroachievements.org/hub/2161?filter%5Bsubsets%5D=only-games&sort=-playersTotal",
  "triggerMasteredGameIds": [1829, 6807, 1483]
}
```

`triggerMasteredGameIds` records the Mastered games that caused that Series to be tracked. It is especially useful when the mastered item is a subset while the Series card intentionally lists base games.

## What is automatic

The GitHub Action now refreshes every registered Series hub automatically. It discovers all **Base Sets Only** games from the public RA Series page, including games that currently have no achievement set. It then uses the official RA API for game metadata and caches those results in `franchises.json`.

On later runs it automatically notices:

- new games added to an already registered Series;
- games removed from a Series;
- games that gain or lose an achievement set;
- changed release information shown by the Series hub;
- newly Mastered games already belonging to a tracked Series.

Games without a set are kept at the bottom of each card. Games within the set/no-set groups are sorted by release date.

## When manual maintenance is still needed

Only when `berti` masters a game whose **primary Series hub is not already in `franchises-source.json`**. Add that Series hub once; after that, its membership stays automatic.

The site deliberately tracks the primary `Series` shown on a game's RA page rather than every `Additional Hub`, which prevents broad overlapping cards such as character/theme hubs from duplicating the collection.
