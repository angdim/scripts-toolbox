# audio_metadata_normalizer/itunes_client/client.py

"""
Минимален HTTP клиент за iTunes Search API.

Използва само стандартната библиотека, защото API-то връща директен JSON и не
изисква OAuth.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


ITUNES_BASE_URL = "https://itunes.apple.com"


class ITunesClient:
    def __init__(self, country: str = "US", timeout: int = 20):
        self.country = country
        self.timeout = timeout

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        url = f"{ITUNES_BASE_URL}{path}?{query}"

        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            return json.load(response)

    def search_albums(self, artist: str, album: str, limit: int = 10) -> list[dict[str, Any]]:
        data = self._get_json(
            "/search",
            {
                "term": f"{artist} {album}",
                "media": "music",
                "entity": "album",
                "limit": limit,
                "country": self.country,
            },
        )
        return list(data.get("results", []))

    def lookup_album_tracks(self, collection_id: int | str) -> list[dict[str, Any]]:
        data = self._get_json(
            "/lookup",
            {
                "id": collection_id,
                "entity": "song",
                "country": self.country,
            },
        )
        return [
            result
            for result in data.get("results", [])
            if result.get("wrapperType") == "track"
        ]
