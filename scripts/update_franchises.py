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

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # local/dev environments may not have it
    curl_requests = None

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


def parse_hub_html(html: str) -> tuple[list[dict[str, Any]], int | None, int | None]:
    """Extract game membership *and visible table metadata* from a Hub page.

    Hub membership is not available in the official Web API, so this is the
    only scraped part of the pipeline.  We deliberately parse the server-side
    table when present because it already contains console, achievement count,
    and release date.  A link-only fallback is retained for layout changes.
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup
    games: list[dict[str, Any]] = []
    seen: set[int] = set()

    # Preferred path: the normal Hub games table. It gives us enough metadata
    # to render the card even if a later API metadata request is rate-limited.
    for row in root.find_all("tr"):
        link = row.find("a", href=re.compile(r"(?:^|retroachievements\.org)/game/\d+"))
        if not link:
            continue
        href = str(link.get("href") or "")
        match = re.search(r"/game/(\d+)", href)
        if not match:
            continue
        game_id = int(match.group(1))
        if game_id in seen:
            continue

        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        title = link.get_text(" ", strip=True)
        if not title:
            image = link.find("img")
            title = str(image.get("alt") or "").strip() if image else ""

        # Current RA table: Title | System | Achievements | Points |
        # RetroRatio | Release Date | Players. Keep this tolerant of columns.
        console = cells[1].get_text(" ", strip=True) if len(cells) > 1 else None
        achievement_count = None
        if len(cells) > 2:
            m = re.search(r"\d[\d,]*", cells[2].get_text(" ", strip=True))
            if m:
                achievement_count = int(m.group(0).replace(",", ""))
        release_date = None
        release_granularity = "day"
        if len(cells) > 5:
            release_date, release_granularity = normalize_release(cells[5].get_text(" ", strip=True))

        seen.add(game_id)
        item: dict[str, Any] = {
            "id": game_id,
            "name": title or f"Game {game_id}",
            "url": f"{BASE}/game/{game_id}",
            "console": console or None,
            "releaseDate": release_date,
            "releaseGranularity": release_granularity,
        }
        if achievement_count is not None:
            item["achievementCount"] = achievement_count
            item["hasSet"] = achievement_count > 0
        games.append(item)

    # Layout-change fallback: discover any canonical game links not captured by
    # the table parser. API enrichment will fill their metadata later.
    for game_link in root.find_all("a", href=True):
        href = str(game_link.get("href") or "")
        match = re.search(r"(?:https?://(?:www\.)?retroachievements\.org)?/game/(\d+)(?:[/?#]|$)", href)
        if not match:
            continue
        game_id = int(match.group(1))
        if game_id in seen:
            continue
        seen.add(game_id)
        title = game_link.get_text(" ", strip=True)
        games.append({
            "id": game_id,
            "name": title or f"Game {game_id}",
            "url": f"{BASE}/game/{game_id}",
        })

    page_count: int | None = None
    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        decoded = href.replace("%5B", "[").replace("%5D", "]")
        match = re.search(r"page\[number\]=(\d+)", decoded)
        if match:
            value = int(match.group(1))
            page_count = max(page_count or 1, value)

    text = soup.get_text(" ", strip=True)
    if page_count is None:
        page_match = re.search(r"Page\s+\d+\s+of\s+(\d+)", text, re.IGNORECASE)
        page_count = int(page_match.group(1)) if page_match else None

    # The page itself prints e.g. "49 games". We use it as an integrity check
    # so a bot-challenge/partial page can never overwrite a full roster.
    expected_count = None
    count_matches = [int(x.replace(",", "")) for x in re.findall(r"(?<![\d,])(\d[\d,]*)\s+games\b", text, re.IGNORECASE)]
    if count_matches:
        expected_count = max(count_matches)

    return games, page_count, expected_count


class HubBrowser:
    """Fetch RA Hub pages with multiple anti-bot compatible strategies."""

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

    @staticmethod
    def _looks_like_hub(html: str) -> bool:
        return "/game/" in html and ("Search games" in html or "search games" in html.lower())

    def get_html(self, url: str) -> str:
        # 1) Normal requests (fastest and normally sufficient).
        try:
            response = self.session.get(url, timeout=35)
            if response.status_code == 200 and self._looks_like_hub(response.text):
                return response.text
            print(f"  requests returned HTTP {response.status_code}; trying browser TLS impersonation…")
        except requests.RequestException as exc:
            print(f"  requests failed ({exc}); trying browser TLS impersonation…")

        # 2) curl_cffi reproduces Chrome's TLS/browser fingerprint. This is much
        # more reliable from GitHub-hosted runners when Cloudflare rejects plain
        # Python requests with HTTP 403.
        if curl_requests is not None:
            try:
                response = curl_requests.get(url, headers=BROWSER_HEADERS, impersonate="chrome", timeout=45)
                if response.status_code == 200 and self._looks_like_hub(response.text):
                    return response.text
                print(f"  curl_cffi returned HTTP {response.status_code}; trying headless Chrome…")
            except Exception as exc:
                print(f"  curl_cffi failed ({exc}); trying headless Chrome…")

        # 3) Final fallback: actual headless Chrome.
        driver = self._ensure_driver()
        driver.get(url)
        time.sleep(2.5)
        html = driver.page_source
        if not self._looks_like_hub(html):
            raise RuntimeError(f"Hub page was blocked or incomplete: {url}")
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
    expected_count: int | None = None

    while page <= (page_count or 50):
        url = hub_page_url(hub_id, page)
        html = browser.get_html(url)
        rows, detected_pages, detected_count = parse_hub_html(html)
        if detected_pages:
            page_count = detected_pages
        if detected_count:
            expected_count = detected_count

        before = len(collected)
        for row in rows:
            collected[int(row["id"])] = row
        added = len(collected) - before
        print(f"  hub {hub_id}: page {page} -> {len(rows)} rows ({added} new; total {len(collected)})")

        if page_count is not None and page >= page_count:
            break
        if page_count is None and (not rows or (page > 1 and added == 0)):
            break
        # Current hub pages commonly expose the complete roster on one page.
        if expected_count is not None and len(collected) >= expected_count:
            break
        page += 1

    if expected_count is not None and len(collected) < expected_count:
        raise RuntimeError(
            f"incomplete hub roster: discovered {len(collected)} of {expected_count} games"
        )
    if not collected:
        raise RuntimeError("no game rows found")

    return list(collected.values())



def jina_reader_url(target_url: str) -> str:
    # Jina Reader acts as a read-only text proxy. This is only used for the
    # public Hub roster when RetroAchievements blocks GitHub-hosted runner IPs.
    # No API key or private data is sent to Jina.
    return "https://r.jina.ai/http://" + target_url.removeprefix("https://").removeprefix("http://")


def parse_jina_markdown(markdown: str) -> tuple[list[dict[str, Any]], int | None, int | None]:
    """Parse a RetroAchievements Hub table rendered as Markdown by Jina Reader."""
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    page_count = None
    m = re.search(r"Page\s+(?:\[Input\]|\d+)\s+of\s+(\d+)", markdown, re.I)
    if m:
        page_count = int(m.group(1))

    expected_count = None
    m = re.search(r"(?:^|\n)\s*(\d+)\s+games\s*(?:$|\n)", markdown, re.I)
    if not m:
        m = re.search(r"(?:^|\n)\s*(\d+)\s+of\s+(\d+)\s+games\s*(?:$|\n)", markdown, re.I)
        if m:
            expected_count = int(m.group(2))
    else:
        expected_count = int(m.group(1))

    for raw in markdown.splitlines():
        line = raw.strip()
        if "|" not in line or "/game/" not in line:
            continue
        # Typical Reader output keeps Markdown links, e.g.
        # [Mega Man](https://retroachievements.org/game/1448) | NES | 48 | ...
        id_match = re.search(r"/game/(\d+)", line)
        if not id_match:
            continue
        game_id = int(id_match.group(1))
        if game_id in seen:
            continue
        parts = [re.sub(r"\s+", " ", p).strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        title = re.sub(r"!?(?:\[([^\]]+)\]\([^)]*\))", r"\1", parts[0]).strip()
        title = re.sub(r"^[-: ]+|[-: ]+$", "", title)
        console = re.sub(r"!?(?:\[([^\]]+)\]\([^)]*\))", r"\1", parts[1]).strip()
        console = re.sub(r"^Image:\s*", "", console, flags=re.I).strip()
        ach_match = re.search(r"\d[\d,]*", parts[2])
        achievement_count = int(ach_match.group(0).replace(",", "")) if ach_match else None
        release_date = None
        release_granularity = "day"
        if len(parts) > 5:
            release_date, release_granularity = normalize_release(parts[5])
        item: dict[str, Any] = {
            "id": game_id,
            "name": title or f"Game {game_id}",
            "url": f"{BASE}/game/{game_id}",
            "console": console or None,
            "releaseDate": release_date,
            "releaseGranularity": release_granularity,
        }
        if achievement_count is not None:
            item["achievementCount"] = achievement_count
            item["hasSet"] = achievement_count > 0
        seen.add(game_id)
        rows.append(item)

    return rows, page_count, expected_count


def scrape_series_via_jina(hub_id: int) -> list[dict[str, Any]]:
    collected: dict[int, dict[str, Any]] = {}
    page = 1
    page_count: int | None = None
    expected_count: int | None = None
    session = requests.Session()
    session.headers.update({"User-Agent": BROWSER_HEADERS["User-Agent"], "Accept": "text/plain,text/markdown,*/*"})

    while page <= (page_count or 50):
        target = hub_page_url(hub_id, page)
        proxy_url = jina_reader_url(target)
        response = session.get(proxy_url, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Jina Reader returned HTTP {response.status_code}")
        rows, detected_pages, detected_count = parse_jina_markdown(response.text)
        if detected_pages:
            page_count = detected_pages
        if detected_count:
            expected_count = detected_count
        before = len(collected)
        for row in rows:
            collected[int(row["id"])] = row
        added = len(collected) - before
        print(f"  Jina hub {hub_id}: page {page} -> {len(rows)} rows ({added} new; total {len(collected)})")
        if page_count is not None and page >= page_count:
            break
        if expected_count is not None and len(collected) >= expected_count:
            break
        if page_count is None and (not rows or (page > 1 and added == 0)):
            break
        page += 1

    if expected_count is not None and len(collected) < expected_count:
        raise RuntimeError(f"Jina roster incomplete: discovered {len(collected)} of {expected_count} games")
    if not collected:
        raise RuntimeError("Jina Reader returned no game rows")
    return list(collected.values())

def api_metadata(api_key: str, game_id: int, checked_at: str) -> dict[str, Any]:
    # Separate clients in worker threads keep retry/backoff state independent.
    client = RetroAchievementsClient(api_key=api_key, min_delay_seconds=0.35)
    data = client.game_extended(game_id)
    achievement_count = int(field(data, "NumAchievements", "numAchievements", default=len(field(data, "Achievements", "achievements", default={}) or {})) or 0)
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
            except Exception as direct_exc:
                print(f"warning: direct Hub access failed for {hub_id}: {direct_exc}")
                print("  trying Jina Reader fallback for the public Hub roster…")
                try:
                    rows = scrape_series_via_jina(hub_id)
                    if not rows:
                        raise RuntimeError("no game rows found through Jina Reader")
                    scraped_by_series[series_id] = rows
                    continue
                except Exception as jina_exc:
                    print(f"warning: Jina Reader fallback failed for hub {hub_id}: {jina_exc}")
                # Preserve the previous generated membership if a site-side
                # change or anti-bot rule temporarily prevents scraping.
                previous_series = next(
                    (item for item in previous.get("series", []) or [] if item.get("id") == series_id),
                    None,
                )
                previous_games = [dict(game) for game in (previous_series or {}).get("games", []) or []]
                trigger_count = len(set(series.get("triggerMasteredGameIds", []) or []))
                # Never create/overwrite a Series with the trigger Mastered games
                # only. That was the bug which produced cards such as 8/8 Mega
                # Man instead of the complete Hub roster. A previously known
                # roster is safe to preserve only if it is clearly larger than
                # the trigger seed.
                if len(previous_games) > trigger_count:
                    print(f"  preserving previous full roster ({len(previous_games)} games)")
                    scraped_by_series[series_id] = previous_games
                else:
                    raise RuntimeError(
                        f"Cannot obtain complete roster for {series.get('name')} (hub {hub_id}); "
                        "refusing to write a trigger-only franchise catalog"
                    )
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
