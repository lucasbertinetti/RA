#!/usr/bin/env python3
"""Build franchises.json from manually mapped RetroAchievements Series hubs.

Why hybrid?
-----------
The official RetroAchievements Web API does not currently expose Series/Hub
membership. `franchises-source.json` therefore contains the *manual* part: the
Series hubs that are relevant to berti's Mastered list.

The list of games inside each Series is then refreshed from the public RA hub
page (Base Sets Only), while game metadata is enriched through the official API.
This gives us two useful properties:

* discovering a brand-new Series still needs an occasional manual edit;
* once a Series is registered, new games added to that Series are picked up
  automatically, including games with no achievement set yet.

`triggerMasteredGameIds` records the Mastered games that caused a Series to be
tracked. This matters for cases where the Mastered item itself is a subset but
the card intentionally lists the Series' base games.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from ra_api import RetroAchievementsAPIError, RetroAchievementsClient

BASE = "https://retroachievements.org"
MEDIA_BASE = "https://media.retroachievements.org"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "franchises-source.json"
OUTPUT = ROOT / "franchises.json"
MASTERED = ROOT / "mastered-games.json"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


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
    if not text:
        return None
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("/Images/"):
        return MEDIA_BASE + text
    if text.startswith("/"):
        return BASE + text
    return text


def normalize_release(value: Any) -> tuple[str | None, str]:
    """Convert the release strings shown in hub tables to ISO-ish values."""
    if value is None:
        return None, "day"
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in {"unknown", "null", "none", "n/a"}:
        return None, "day"

    # Already ISO-like.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", text):
        return text[:10], "day"
    if re.fullmatch(r"\d{4}", text):
        return text, "year"

    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d"), "day"
        except ValueError:
            pass
    for fmt in ("%b %Y", "%B %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m"), "month"
        except ValueError:
            pass

    return text, "day"


def previous_cache(previous: dict[str, Any]) -> dict[int, dict[str, Any]]:
    cache: dict[int, dict[str, Any]] = {}
    for series in previous.get("series", []) or []:
        for game in series.get("games", []) or []:
            try:
                cache[int(game["id"])] = game
            except (KeyError, TypeError, ValueError):
                pass
    return cache


def mastered_cache(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for group in ("mastered", "beaten"):
        for game in snapshot.get(group, []) or []:
            try:
                result[int(game["id"])] = game
            except (KeyError, TypeError, ValueError):
                pass
    return result


def hub_page_url(hub_id: int, page: int) -> str:
    params = {
        "filter[subsets]": "only-games",
        "sort": "releasedAt",
    }
    if page > 1:
        params["page[number]"] = str(page)
    return f"{BASE}/hub/{hub_id}?{urlencode(params)}"


def parse_hub_html(html: str) -> tuple[list[dict[str, Any]], int | None]:
    """Extract the complete game roster from a Series hub page.

    RA has changed the hub presentation over time (tables, cards, responsive
    layouts).  The previous updater only inspected ``table tr`` rows, which
    meant a layout change could make the refresh fall back to the manually
    seeded mastered IDs.  Here membership is determined from every canonical
    ``/game/<id>`` link in the page's main content.  Detailed metadata is then
    obtained from the official API, so the scraper only needs to discover IDs.
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup
    games: list[dict[str, Any]] = []
    seen: set[int] = set()

    for game_link in root.find_all("a", href=True):
        href = str(game_link.get("href") or "")
        match = re.fullmatch(r"/game/(\d+)(?:[/?#].*)?", href)
        if not match:
            # Absolute links occasionally appear in rendered/fallback markup.
            match = re.fullmatch(r"https?://(?:www\.)?retroachievements\.org/game/(\d+)(?:[/?#].*)?", href)
        if not match:
            continue

        game_id = int(match.group(1))
        if game_id in seen:
            continue
        seen.add(game_id)

        title = game_link.get_text(" ", strip=True)
        if not title:
            image = game_link.find("img")
            if image:
                title = str(image.get("alt") or "").strip()

        games.append({
            "id": game_id,
            "name": title or f"Game {game_id}",
            "url": f"{BASE}/game/{game_id}",
        })

    # Find the maximum page number from pagination links.  This is more robust
    # than depending only on visible "Page X of Y" text.
    page_count: int | None = None
    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        decoded = href.replace("%5B", "[").replace("%5D", "]")
        match = re.search(r"page\[number\]=(\d+)", decoded)
        if match:
            value = int(match.group(1))
            page_count = max(page_count or 1, value)

    if page_count is None:
        text = soup.get_text(" ", strip=True)
        page_match = re.search(r"Page\s+\d+\s+of\s+(\d+)", text, re.IGNORECASE)
        page_count = int(page_match.group(1)) if page_match else None

    return games, page_count


class HubBrowser:
    """Requests-first fetcher with a real-browser fallback for RA anti-bot rules."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.driver = None

    def _ensure_driver(self):
        if self.driver is not None:
            return self.driver
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,1200")
        options.add_argument(f"--user-agent={BROWSER_HEADERS['User-Agent']}")
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(60)
        return self.driver

    def get_html(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=35)
            if response.status_code == 200 and "/game/" in response.text:
                return response.text
            print(f"  requests returned HTTP {response.status_code}; trying headless Chrome…")
        except requests.RequestException as exc:
            print(f"  requests failed ({exc}); trying headless Chrome…")

        driver = self._ensure_driver()
        driver.get(url)
        # The hub table is server-rendered in normal operation; this small wait
        # also gives any bot-check/navigation JS time to settle.
        time.sleep(1.5)
        html = driver.page_source
        if "/game/" not in html:
            raise RuntimeError(f"Hub page did not expose game rows: {url}")
        return html

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass


def scrape_series(browser: HubBrowser, hub_id: int) -> list[dict[str, Any]]:
    collected: dict[int, dict[str, Any]] = {}
    page = 1
    page_count: int | None = None

    while page <= (page_count or 20):
        url = hub_page_url(hub_id, page)
        html = browser.get_html(url)
        rows, detected_pages = parse_hub_html(html)
        if detected_pages:
            page_count = detected_pages

        before = len(collected)
        for row in rows:
            collected[int(row["id"])] = row
        added = len(collected) - before
        print(f"  hub {hub_id}: page {page} -> {len(rows)} rows ({added} new)")

        # If pagination markup is unavailable, stop when the next request stops
        # adding new IDs. For a normal one-page hub, fewer than 50 rows is enough.
        if page_count is not None and page >= page_count:
            break
        if page_count is None and (not rows or (page > 1 and added == 0) or len(rows) < 50):
            break
        page += 1

    return list(collected.values())


def api_metadata(api_key: str, game_id: int, checked_at: str) -> dict[str, Any]:
    # Separate clients in worker threads keep retry/backoff state independent.
    client = RetroAchievementsClient(api_key=api_key, min_delay_seconds=0.35)
    data = client.game_extended(game_id)
    achievement_count = int(field(data, "NumAchievements", "numAchievements", default=0) or 0)
    release_date, granularity = normalize_release(field(
        data,
        "Released", "released",
        "ReleaseDate", "releaseDate",
        "ReleasedAt", "releasedAt",
    ))
    granularity = field(
        data,
        "ReleasedAtGranularity", "releasedAtGranularity",
        "ReleaseDateGranularity", "releaseDateGranularity",
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


def merge_metadata(
    game_id: int,
    scraped: dict[str, Any] | None,
    api_game: dict[str, Any] | None,
    old: dict[str, Any] | None,
    local_progress: dict[str, Any] | None,
    checked_at: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": game_id,
        "name": f"Game {game_id}",
        "url": f"{BASE}/game/{game_id}",
        "icon": None,
        "console": None,
        "releaseDate": None,
        "releaseGranularity": "day",
        "achievementCount": 0,
        "hasSet": False,
        "metadataCheckedAt": checked_at,
    }
    for source in (old, scraped, api_game):
        if source:
            for key, value in source.items():
                if value is not None:
                    result[key] = value

    # The current user's snapshot is a very good local source for icons and full
    # console names of games they have actually played.
    if local_progress:
        if local_progress.get("icon"):
            result["icon"] = local_progress["icon"]
        if local_progress.get("console"):
            result["console"] = local_progress["console"]
        if local_progress.get("name"):
            result["name"] = local_progress["name"]

    # Hub scraping is deliberately used only for membership discovery.  When
    # a rendered hub also exposes extra metadata, accept it without treating
    # missing scraper fields as authoritative zero/false values.
    if scraped:
        if "achievementCount" in scraped:
            result["achievementCount"] = int(scraped.get("achievementCount") or 0)
            result["hasSet"] = bool(scraped.get("hasSet"))
        if scraped.get("releaseDate"):
            result["releaseDate"] = scraped["releaseDate"]
            result["releaseGranularity"] = scraped.get("releaseGranularity") or "day"

    return result


def release_sort_key(game: dict[str, Any]) -> tuple[int, int, str, str]:
    # Requirement: no-set games go at the end. Each block is chronological.
    no_set = 0 if game.get("hasSet") else 1
    unknown_release = 0 if game.get("releaseDate") else 1
    release = str(game.get("releaseDate") or "9999-99-99")
    return no_set, unknown_release, release, str(game.get("name") or "")


def metadata_age_days(game: dict[str, Any] | None, now: datetime) -> float | None:
    if not game:
        return None
    raw = str(game.get("metadataCheckedAt") or "").strip()
    if not raw:
        return None
    try:
        checked = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return max(0.0, (now - checked).total_seconds() / 86400.0)
    except ValueError:
        return None


def needs_api_refresh(game: dict[str, Any] | None, now: datetime) -> bool:
    if not game:
        return True

    # Missing release dates were the source of the old "Unknown release"
    # labels.  Re-query those immediately in case RA now has the metadata.
    required = ("name", "console", "icon", "releaseDate")
    if any(not game.get(key) for key in required):
        return True

    age = metadata_age_days(game, now)
    if age is None:
        return True

    # Recheck no-set entries relatively often so a newly created achievement
    # set appears automatically.  Established sets need much less frequent
    # metadata refreshes.
    return age >= (7 if not game.get("hasSet") else 180)

def main() -> int:
    api_key = os.getenv("RA_API_KEY", "").strip()
    if not api_key:
        print("error: RA_API_KEY is not set", file=sys.stderr)
        return 2

    source = load_json(SOURCE, {"series": []})
    previous = load_json(OUTPUT, {"series": []})
    progress = load_json(MASTERED, {"mastered": [], "beaten": []})
    old_by_id = previous_cache(previous)
    progress_by_id = mastered_cache(progress)
    now = datetime.now(timezone.utc)
    checked_at = now.isoformat().replace("+00:00", "Z")

    browser = HubBrowser()
    scraped_by_series: dict[str, list[dict[str, Any]]] = {}
    try:
        for series in source.get("series", []) or []:
            series_id = str(series.get("id") or "")
            hub_id = int(series.get("hubId") or 0)
            if not series_id or not hub_id:
                continue
            print(f"Reading Series hub: {series.get('name')} ({hub_id})")
            try:
                rows = scrape_series(browser, hub_id)
                if not rows:
                    raise RuntimeError("no game rows found")
                scraped_by_series[series_id] = rows
            except Exception as exc:
                print(f"warning: could not refresh hub {hub_id}: {exc}")
                # Preserve the previous generated membership if a site-side
                # change or anti-bot rule temporarily prevents scraping.
                previous_series = next(
                    (item for item in previous.get("series", []) or [] if item.get("id") == series_id),
                    None,
                )
                if previous_series:
                    scraped_by_series[series_id] = [dict(game) for game in previous_series.get("games", []) or []]
                else:
                    # Last-resort seed: the Series still appears with the games
                    # that caused us to track it; a future successful run fills
                    # the complete roster automatically.
                    scraped_by_series[series_id] = [
                        {"id": int(game_id), "url": f"{BASE}/game/{int(game_id)}"}
                        for game_id in series.get("triggerMasteredGameIds", []) or []
                    ]
    finally:
        browser.close()

    unique_ids: set[int] = set()
    scraped_by_id: dict[int, dict[str, Any]] = {}
    for rows in scraped_by_series.values():
        for row in rows:
            try:
                game_id = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            unique_ids.add(game_id)
            scraped_by_id[game_id] = row

    # Fetch brand-new games and periodically refresh cached metadata.  In
    # particular, games with no known release date are retried immediately and
    # no-set entries are rechecked weekly.
    ids_to_fetch = sorted(
        game_id for game_id in unique_ids
        if needs_api_refresh(old_by_id.get(game_id), now)
    )
    api_results: dict[int, dict[str, Any]] = {}
    if ids_to_fetch:
        workers = max(1, min(int(os.getenv("FRANCHISE_API_WORKERS", "3")), 6))
        print(f"Fetching official API metadata for {len(ids_to_fetch)} new/stale games with {workers} workers…")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(api_metadata, api_key, game_id, checked_at): game_id for game_id in ids_to_fetch}
            done = 0
            for future in as_completed(futures):
                game_id = futures[future]
                done += 1
                try:
                    api_results[game_id] = future.result()
                except (RetroAchievementsAPIError, Exception) as exc:
                    print(f"warning: metadata for game {game_id}: {exc}")
                if done == 1 or done % 25 == 0 or done == len(ids_to_fetch):
                    print(f"  metadata progress: {done}/{len(ids_to_fetch)}")

    normalized_by_id: dict[int, dict[str, Any]] = {}
    for game_id in unique_ids:
        normalized_by_id[game_id] = merge_metadata(
            game_id,
            scraped_by_id.get(game_id),
            api_results.get(game_id),
            old_by_id.get(game_id),
            progress_by_id.get(game_id),
            checked_at,
        )

    output_series: list[dict[str, Any]] = []
    for series in source.get("series", []) or []:
        series_id = str(series.get("id") or "")
        rows = scraped_by_series.get(series_id, [])
        ids: list[int] = []
        seen: set[int] = set()
        for row in rows:
            try:
                game_id = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if game_id not in seen:
                seen.add(game_id)
                ids.append(game_id)
        games = [normalized_by_id[game_id] for game_id in ids if game_id in normalized_by_id]
        games.sort(key=release_sort_key)
        triggers = sorted({int(x) for x in series.get("triggerMasteredGameIds", []) or []})
        output_series.append({
            "id": series_id,
            "name": series.get("name") or "Unnamed series",
            "hubId": series.get("hubId"),
            "hubUrl": series.get("hubUrl") or f"{BASE}/hub/{series.get('hubId')}",
            "triggerMasteredGameIds": triggers,
            "games": games,
        })

    payload = {
        "schemaVersion": 2,
        "generatedAt": checked_at,
        "sourceAudit": source.get("lastManualSeriesAudit"),
        "series": output_series,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(output_series)} Series and {len(unique_ids)} unique games to {OUTPUT.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
