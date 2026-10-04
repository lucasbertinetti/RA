#!/usr/bin/env python3
"""Build mastered-games.json from berti's public RetroAchievements pages.

This script deliberately does not use the official RetroAchievements API because
that API requires a private web API key. It only reads public HTML pages.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

BASE = "https://retroachievements.org"
USERNAME = "berti"
OUTPUT = Path(__file__).resolve().parents[1] / "mastered-games.json"

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
DATE_RE = re.compile(rf"\b(?:{MONTHS})\s+\d{{1,2}}\s+\d{{4}}\b")
GAME_HREF_RE = re.compile(r"^/game/(\d+)(?:$|[/?#])")

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (compatible; berti-RA-gallery/1.0; "
            "+https://lucasbertinetti.github.io/RA/)"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
)


def fetch(url: str, *, params: dict | None = None) -> BeautifulSoup:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = SESSION.get(url, params=params, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_icon(src: str | None) -> str | None:
    if not src:
        return None
    src = src.strip()
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        # Game icons are normally served by media.retroachievements.org.
        if src.startswith("/Images/"):
            return "https://media.retroachievements.org" + src
        return BASE + src
    return src


def candidate_card(anchor: Tag, verb: str) -> Tag | None:
    """Find the smallest ancestor that contains one complete progress record."""
    node: Tag | None = anchor
    best: Tag | None = None
    for _ in range(10):
        if node is None or not isinstance(node, Tag):
            break
        text = clean(node.get_text(" ", strip=True))
        if f"{verb} in " in text and DATE_RE.search(text):
            best = node
            # Prefer a compact row/card. Once it is reasonably small, stop.
            if len(text) < 900:
                break
        parent = node.parent
        node = parent if isinstance(parent, Tag) else None
    return best


def extract_progress(status: str) -> list[dict]:
    if status == "mastered":
        filter_status = "gte-completed"
        verb = "Mastered"
    else:
        filter_status = "any-beaten"
        verb = "Beaten"

    soup = fetch(
        f"{BASE}/user/{USERNAME}/progress",
        params={"filter[status]": filter_status, "filter[system]": "0"},
    )

    records: list[dict] = []
    seen: set[int] = set()

    for anchor in soup.find_all("a", href=GAME_HREF_RE):
        href = anchor.get("href", "")
        match = GAME_HREF_RE.match(href)
        if not match:
            continue
        game_id = int(match.group(1))
        if game_id in seen:
            continue

        name = clean(anchor.get_text(" ", strip=True))
        if not name:
            continue

        card = candidate_card(anchor, verb)
        if card is None:
            continue

        text = clean(card.get_text(" ", strip=True))
        date_match = DATE_RE.search(text)
        time_match = re.search(
            rf"{verb}\s+in\s+(.+?)(?=(?:\s+\d{{1,3}}%|\s*$))",
            text,
            flags=re.IGNORECASE,
        )

        # A broad fallback protects against markup changes where the percentage
        # isn't in the same wrapper as the status text.
        if not time_match:
            time_match = re.search(
                rf"{verb}\s+in\s+(.+)", text, flags=re.IGNORECASE
            )

        icon = None
        for img in card.find_all("img"):
            src = normalize_icon(img.get("src") or img.get("data-src"))
            alt = clean(img.get("alt", ""))
            if src and ("/Images/" in src or name.lower() in alt.lower()):
                icon = src
                break

        seen.add(game_id)
        records.append(
            {
                "id": game_id,
                "name": name,
                "url": urljoin(BASE, href),
                "icon": icon,
                "date": date_match.group(0) if date_match else None,
                "time": clean(time_match.group(1)) if time_match else None,
                "console": None,
                "genre": None,
            }
        )

    if not records:
        raise RuntimeError(f"No {status} games were found on the public profile page")

    return records


def extract_game_metadata(game: dict) -> dict:
    soup = fetch(game["url"])

    # Console: the page title is consistently "Game Name (Console) · RetroAchievements".
    title = clean(soup.title.get_text(" ", strip=True)) if soup.title else ""
    title_match = re.search(r"\(([^()]*)\)\s*[·|-]\s*RetroAchievements\s*$", title)
    if title_match:
        game["console"] = clean(title_match.group(1))

    # Genre: find the metadata label and use the first value/link in that row.
    genre_label = soup.find(string=lambda s: isinstance(s, str) and clean(s) == "Genre")
    if genre_label:
        label_tag = genre_label.parent if isinstance(genre_label.parent, Tag) else None
        container = label_tag
        for _ in range(4):
            if container is None:
                break
            row_text = clean(container.get_text(" ", strip=True))
            if row_text.startswith("Genre") and len(row_text) > len("Genre"):
                links = container.find_all("a")
                genre_candidates = [clean(a.get_text(" ", strip=True)) for a in links]
                genre_candidates = [g for g in genre_candidates if g and g != "Genre"]
                if genre_candidates:
                    game["genre"] = genre_candidates[0]
                else:
                    value = clean(re.sub(r"^Genre\s*", "", row_text, flags=re.I))
                    if value:
                        game["genre"] = re.split(r"[,/|]", value, maxsplit=1)[0].strip()
                break
            parent = container.parent
            container = parent if isinstance(parent, Tag) else None

    # Icon: prefer an image whose alt matches the game title.
    if not game.get("icon"):
        target = clean(game["name"]).casefold()
        for img in soup.find_all("img"):
            alt = clean(img.get("alt", "")).casefold()
            src = normalize_icon(img.get("src") or img.get("data-src"))
            if src and target and (alt == target or target in alt):
                game["icon"] = src
                break

    return game


def enrich(records: list[dict]) -> list[dict]:
    total = len(records)
    for index, game in enumerate(records, start=1):
        try:
            extract_game_metadata(game)
        except Exception as exc:  # keep the snapshot usable if one game page fails
            print(f"warning: metadata failed for {game['name']} ({game['id']}): {exc}")

        # Public pages are being scraped politely and sequentially.
        time.sleep(0.35)

        # The profile sorts newest first. Numbering backwards means the newest
        # entry receives the current highest sequence number (#100, #99, ...).
        game["number"] = total - index + 1

    return records


def main() -> None:
    print("Reading mastered games...")
    mastered = enrich(extract_progress("mastered"))

    print("Reading beaten games...")
    beaten = enrich(extract_progress("beaten"))

    # Defensive deduplication: if RetroAchievements ever changes the beaten
    # filter to include mastered games, mastered wins and the duplicate is removed.
    mastered_ids = {game["id"] for game in mastered}
    beaten = [game for game in beaten if game["id"] not in mastered_ids]
    for index, game in enumerate(beaten, start=1):
        game["number"] = len(beaten) - index + 1

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": f"{BASE}/user/{USERNAME}",
        "mastered": mastered,
        "beaten": beaten,
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(mastered)} mastered and {len(beaten)} beaten games to {OUTPUT}")


if __name__ == "__main__":
    main()
