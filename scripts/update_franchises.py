#!/usr/bin/env python3
"""Build franchises.json from the manually curated Series catalog.

Hub membership is NEVER scraped here. `franchises-source.json` is authoritative
for audited Series. Official RA API calls are used only to refresh metadata for
known game IDs. Mastered checks remain client-side via mastered-games.json.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ra_api import RetroAchievementsAPIError, RetroAchievementsClient

BASE = "https://retroachievements.org"
MEDIA_BASE = "https://media.retroachievements.org"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "franchises-source.json"
OUTPUT = ROOT / "franchises.json"
MASTERED = ROOT / "mastered-games.json"

def field(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return default

def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

def normalize_icon(path: str | None) -> str | None:
    if not path:
        return None
    text = str(path).strip()
    if text.startswith("/Images/"):
        return MEDIA_BASE + text
    if text.startswith("/"):
        return BASE + text
    return text or None

def normalize_release(value: Any) -> tuple[str | None, str]:
    if value is None:
        return None, "day"
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "null", "none", "n/a"}:
        return None, "day"
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10], "day"
    if len(text) == 7 and text[4:5] == "-":
        return text, "month"
    if len(text) == 4 and text.isdigit():
        return text, "year"
    return text, "day"

def previous_series_by_id(previous: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(s.get("id")): s for s in previous.get("series", []) or [] if s.get("id")}

def previous_games_by_id(previous: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out = {}
    for s in previous.get("series", []) or []:
        for g in s.get("games", []) or []:
            try:
                out[int(g["id"])] = g
            except (KeyError, TypeError, ValueError):
                pass
    return out

def progress_games_by_id(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out = {}
    for group in ("mastered", "beaten"):
        for g in snapshot.get(group, []) or []:
            try:
                out[int(g["id"])] = g
            except (KeyError, TypeError, ValueError):
                pass
    return out

def api_metadata(api_key: str, game_id: int, checked_at: str) -> dict[str, Any]:
    client = RetroAchievementsClient(api_key=api_key, min_delay_seconds=0.35)
    data = client.game_extended(game_id)
    achievement_count = int(field(
        data, "NumAchievements", "numAchievements",
        default=len(field(data, "Achievements", "achievements", default={}) or {})
    ) or 0)
    release_date, granularity = normalize_release(field(
        data, "Released", "released", "ReleaseDate", "releaseDate",
        "ReleasedAt", "releasedAt"
    ))
    granularity = field(
        data, "ReleasedAtGranularity", "releasedAtGranularity",
        "ReleaseDateGranularity", "releaseDateGranularity"
    ) or granularity
    return {
        "id": game_id,
        "name": field(data, "Title", "title") or f"Game {game_id}",
        "url": f"{BASE}/game/{game_id}",
        "icon": normalize_icon(field(data, "ImageIcon", "imageIcon")),
        "console": field(data, "ConsoleName", "consoleName"),
        "releaseDate": release_date,
        "releaseGranularity": granularity or "day",
        "achievementCount": achievement_count,
        "hasSet": achievement_count > 0,
        "metadataCheckedAt": checked_at,
    }

def release_sort_key(game: dict[str, Any]):
    # Games with achievement sets first, chronologically; no-set games last.
    no_set = 0 if game.get("hasSet") else 1
    unknown_release = 0 if game.get("releaseDate") else 1
    release = str(game.get("releaseDate") or "9999-99-99")
    return no_set, unknown_release, release, str(game.get("name") or "")

def merge_game(manual, api_game, old, progress, checked_at):
    game_id = int(manual["id"])
    result = {
        "id": game_id,
        "name": manual.get("name") or f"Game {game_id}",
        "url": f"{BASE}/game/{game_id}",
        "icon": None,
        "console": manual.get("console"),
        "releaseDate": manual.get("releaseDate"),
        "releaseGranularity": manual.get("releaseGranularity") or "day",
        "achievementCount": int(manual.get("achievementCount") or 0),
        "hasSet": bool(manual.get("hasSet")),
        "metadataCheckedAt": checked_at,
    }
    # Old/API may enrich icon and naming, but the manual Hub audit remains the
    # authority for membership, release ordering and no-set status when supplied.
    for src in (old, api_game):
        if not src:
            continue
        for key in ("name", "url", "icon", "console"):
            if src.get(key):
                result[key] = src[key]
    if api_game:
        # The official API is allowed to refresh achievement-set status.
        result["achievementCount"] = int(api_game.get("achievementCount") or 0)
        result["hasSet"] = bool(api_game.get("hasSet"))
        if api_game.get("releaseDate"):
            result["releaseDate"] = api_game["releaseDate"]
            result["releaseGranularity"] = api_game.get("releaseGranularity") or "day"
    if progress:
        for key in ("name", "icon", "console"):
            if progress.get(key):
                result[key] = progress[key]
    return result

def main() -> int:
    api_key = os.getenv("RA_API_KEY", "").strip()
    source = load_json(SOURCE, {"series": []})
    previous = load_json(OUTPUT, {"series": []})
    progress = load_json(MASTERED, {"mastered": [], "beaten": []})

    prev_series = previous_series_by_id(previous)
    old_games = previous_games_by_id(previous)
    progress_games = progress_games_by_id(progress)
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Only audited Series have a `games` array. Unaudited Series preserve their
    # previous generated card unchanged until their turn in the manual audit.
    rosters = {}
    unique_ids = set()
    for s in source.get("series", []) or []:
        sid = str(s.get("id") or "")
        manual_games = s.get("games")
        if isinstance(manual_games, list):
            roster = manual_games
        else:
            roster = [dict(g) for g in (prev_series.get(sid, {}).get("games", []) or [])]
        rosters[sid] = roster
        for g in roster:
            try:
                unique_ids.add(int(g["id"]))
            except (KeyError, TypeError, ValueError):
                pass

    api_results = {}
    if api_key and unique_ids:
        workers = max(1, min(int(os.getenv("FRANCHISE_API_WORKERS", "3")), 6))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(api_metadata, api_key, gid, checked_at): gid for gid in sorted(unique_ids)}
            for future in as_completed(futures):
                gid = futures[future]
                try:
                    api_results[gid] = future.result()
                except (RetroAchievementsAPIError, Exception) as exc:
                    print(f"warning: metadata for game {gid}: {exc}")
    elif not api_key:
        print("warning: RA_API_KEY is not set; using manual/cached metadata only", file=sys.stderr)

    output_series = []
    for s in source.get("series", []) or []:
        sid = str(s.get("id") or "")
        games = []
        for manual in rosters.get(sid, []):
            try:
                gid = int(manual["id"])
            except (KeyError, TypeError, ValueError):
                continue
            games.append(merge_game(
                manual, api_results.get(gid), old_games.get(gid),
                progress_games.get(gid), checked_at
            ))
        games.sort(key=release_sort_key)
        output_series.append({
            "id": sid,
            "name": s.get("name") or "Unnamed series",
            "hubId": s.get("hubId"),
            "hubUrl": s.get("hubUrl") or f"{BASE}/hub/{s.get('hubId')}",
            "triggerMasteredGameIds": sorted({int(x) for x in s.get("triggerMasteredGameIds", []) or []}),
            "games": games,
        })

    payload = {
        "schemaVersion": 3,
        "generatedAt": checked_at,
        "sourceAudit": source.get("lastManualSeriesAudit"),
        "series": output_series,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(output_series)} Series and {len(unique_ids)} known games to {OUTPUT.name}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
