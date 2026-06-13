# audio_metadata_normalizer/itunes_client/search.py

"""Търсене на албуми през iTunes Search API."""

from typing import Any


def search_album(client, artist: str, album: str) -> list[dict[str, Any]]:
    if not artist or not album:
        raise ValueError("search_album() requires both artist and album")

    return client.search_albums(artist, album)
