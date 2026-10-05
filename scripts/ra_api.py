#!/usr/bin/env python3
"""Small RetroAchievements Web API client used by the site data updater.

Only Python's standard library is used so the GitHub Action does not need to
install third-party packages. API keys are read by the caller from environment
variables and are never written to disk.
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://retroachievements.org/API"
USER_AGENT = "berti-ra-site/2.0 (+https://lucasbertinetti.github.io/RA/)"


class RetroAchievementsAPIError(RuntimeError):
    """Raised when the RetroAchievements API cannot be read successfully."""


@dataclass(frozen=True)
class RetroAchievementsClient:
    api_key: str
    timeout: int = 45
    retries: int = 5
    min_delay_seconds: float = 0.12

    def _get(self, endpoint: str, params: dict[str, Any]) -> Any:
        query = {**params, "y": self.api_key}
        url = f"{API_BASE}/{endpoint}?{urlencode(query)}"
        last_error: Exception | None = None
        for attempt in range(self.retries):
            request = Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8")
                time.sleep(self.min_delay_seconds)
                return json.loads(body)
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 20)
                time.sleep(wait)
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(min(2 ** attempt, 20))
        safe_url = f"{API_BASE}/{endpoint}"
        raise RetroAchievementsAPIError(
            f"RetroAchievements API request failed: {safe_url}: {last_error}"
        )

    def user_completion_progress(
        self,
        username: str,
        *,
        count: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._get(
            "API_GetUserCompletionProgress.php",
            {"u": username, "c": count, "o": offset},
        )

    def game_info_and_user_progress(
        self,
        username: str,
        game_id: int,
    ) -> dict[str, Any]:
        return self._get(
            "API_GetGameInfoAndUserProgress.php",
            {"u": username, "g": game_id, "a": 1},
        )

    def game_extended(self, game_id: int) -> dict[str, Any]:
        """Return official metadata for a known RA game ID."""
        return self._get("API_GetGameExtended.php", {"i": game_id})
