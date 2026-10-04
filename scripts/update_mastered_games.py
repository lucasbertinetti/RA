#!/usr/bin/env python3
"""Refresh mastered-games.json from the official RetroAchievements Web API.

Required environment variable:
    RA_API_KEY   RetroAchievements Web API key (store as a GitHub Actions secret)

Optional environment variable:
    RA_USERNAME  Target username. Defaults to "berti".

The first run may make one detail request for every mastered/beaten game. Later
runs reuse details from mastered-games.json and normally make only the single
completion-progress request plus detail requests for new/status-changed games.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ra_api import RetroAchievementsClient, RetroAchievementsAPIError

BASE = "https://retroachievements.org"
MEDIA_BASE = "https://media.retroachievements.org"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "mastered-games.json"
USERNAME = os.getenv("RA_USERNAME", "berti").strip() or "berti"

# Mirror the dedicated RA status lists: Mastered (all achievements in hardcore)
# and Beaten (hardcore win condition/progression, but not mastered). Completed
# and beaten-softcore are intentionally not included.
MASTERED_KINDS = {"mastered"}
BEATEN_KINDS = {"beaten-hardcore"}


def field(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return default


def normalize_icon(path: str | None) -> str | None:
    if not path:
        return None
    path = str(path).strip()
    if not path:
        return None
    if path.startswith("//"):
        return "https:" + path
    if path.startswith("/Images/"):
        return MEDIA_BASE + path
    if path.startswith("/"):
        return BASE + path
    return path


def first_genre(value: str | None) -> str | None:
    """Return only the first genre when RA stores multiple genres in one field."""
    if not value:
        return None
    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    # RA genre strings may contain several labels. The site only displays the
    # first one, as requested.
    for separator in (",", "/", "|", ";"):
        if separator in text:
            text = text.split(separator, 1)[0].strip()
    return text or None


def load_previous() -> dict[str, Any]:
    if not OUTPUT.exists():
        return {}
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def previous_by_id(previous: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for section in ("mastered", "beaten"):
        for game in previous.get(section, []) or []:
            try:
                result[int(game["id"])] = game
            except (KeyError, TypeError, ValueError):
                continue
    return result


def fetch_all_progress(client: RetroAchievementsClient) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    page_size = 500

    while True:
        payload = client.user_completion_progress(
            USERNAME, count=page_size, offset=offset
        )
        page = field(payload, "Results", "results", default=[]) or []
        records.extend(page)

        total = int(field(payload, "Total", "total", default=len(records)) or 0)
        offset += len(page)
        if not page or offset >= total:
            break

    return records


def base_record(progress: dict[str, Any]) -> dict[str, Any]:
    game_id = int(field(progress, "GameID", "gameId"))
    award_kind = field(progress, "HighestAwardKind", "highestAwardKind")
    award_date = field(progress, "HighestAwardDate", "highestAwardDate")
    return {
        "id": game_id,
        "name": field(progress, "Title", "title") or f"Game {game_id}",
        "url": f"{BASE}/game/{game_id}",
        "icon": normalize_icon(field(progress, "ImageIcon", "imageIcon")),
        "console": field(progress, "ConsoleName", "consoleName"),
        "genre": None,
        "awardKind": award_kind,
        "awardDate": award_date,
        "playtimeSeconds": None,
    }


def can_reuse(old: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    if not old:
        return False
    if old.get("awardKind") != current.get("awardKind"):
        return False
    # If metadata was missing on an earlier transient API failure, retry it.
    if not old.get("genre") or old.get("playtimeSeconds") is None:
        return False
    return True


def enrich(
    client: RetroAchievementsClient,
    current: dict[str, Any],
    old: dict[str, Any] | None,
) -> dict[str, Any]:
    if can_reuse(old, current):
        return {
            **current,
            "genre": old.get("genre"),
            "playtimeSeconds": old.get("playtimeSeconds"),
        }

    details = client.game_info_and_user_progress(USERNAME, current["id"])
    return {
        **current,
        "name": field(details, "Title", "title", default=current["name"]),
        "icon": normalize_icon(
            field(details, "ImageIcon", "imageIcon", default=current["icon"])
        ),
        "console": field(
            details, "ConsoleName", "consoleName", default=current["console"]
        ),
        "genre": first_genre(field(details, "Genre", "genre")),
        "playtimeSeconds": field(
            details, "UserTotalPlaytime", "userTotalPlaytime", default=None
        ),
    }


def sort_and_number(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Newest award first. ISO-8601 timestamps sort chronologically as strings.
    games.sort(key=lambda game: game.get("awardDate") or "", reverse=True)
    total = len(games)
    for index, game in enumerate(games):
        # "Last to first": newest is #N and the oldest is #1.
        game["number"] = total - index
    return games


def build_snapshot(client: RetroAchievementsClient) -> dict[str, Any]:
    previous = load_previous()
    cache = previous_by_id(previous)
    progress = fetch_all_progress(client)

    mastered: list[dict[str, Any]] = []
    beaten: list[dict[str, Any]] = []

    selected = []
    for item in progress:
        award_kind = field(item, "HighestAwardKind", "highestAwardKind")
        if award_kind in MASTERED_KINDS or award_kind in BEATEN_KINDS:
            selected.append(item)

    print(
        f"Found {len(selected)} mastered/beaten records among "
        f"{len(progress)} played games."
    )

    for index, item in enumerate(selected, start=1):
        current = base_record(item)
        game_id = current["id"]
        reused = can_reuse(cache.get(game_id), current)
        label = "cached" if reused else "API"
        print(
            f"[{index}/{len(selected)}] {current['name']} "
            f"({current['awardKind']}) [{label}]"
        )
        try:
            game = enrich(client, current, cache.get(game_id))
        except RetroAchievementsAPIError as exc:
            # Do not destroy a good historical snapshot because one detail call
            # failed. Reuse old details if available, otherwise keep the base data.
            print(f"warning: detail lookup failed for game {game_id}: {exc}")
            old = cache.get(game_id) or {}
            game = {
                **current,
                "genre": old.get("genre"),
                "playtimeSeconds": old.get("playtimeSeconds"),
            }

        if game["awardKind"] in MASTERED_KINDS:
            mastered.append(game)
        elif game["awardKind"] in BEATEN_KINDS:
            beaten.append(game)

    mastered = sort_and_number(mastered)
    beaten = sort_and_number(beaten)

    return {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": f"{BASE}/user/{USERNAME}",
        "username": USERNAME,
        "mastered": mastered,
        "beaten": beaten,
    }


def main() -> int:
    api_key = os.getenv("RA_API_KEY", "").strip()
    if not api_key:
        print(
            "error: RA_API_KEY is not set. Add it as a GitHub Actions repository "
            "secret named RA_API_KEY.",
            file=sys.stderr,
        )
        return 2

    client = RetroAchievementsClient(api_key=api_key)
    try:
        payload = build_snapshot(client)
    except RetroAchievementsAPIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(payload['mastered'])} mastered and "
        f"{len(payload['beaten'])} beaten games to {OUTPUT.name}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
