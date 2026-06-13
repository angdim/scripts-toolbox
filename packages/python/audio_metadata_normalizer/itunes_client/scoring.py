# audio_metadata_normalizer/itunes_client/scoring.py

"""Scoring модул за iTunes Search API резултати."""

from difflib import SequenceMatcher
from typing import Any

from audio_metadata_normalizer.utils.normalize import (
    normalize_album,
    normalize_artist,
)


def fuzzy(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def score_release(result: dict[str, Any], artist: str, album: str) -> float:
    score = 0.0

    artist_n = normalize_artist(artist)
    album_n = normalize_album(album)

    score += fuzzy(artist_n, normalize_artist(result.get("artistName", ""))) * 55
    score += fuzzy(album_n, normalize_album(result.get("collectionName", ""))) * 55

    if result.get("wrapperType") == "collection":
        score += 10

    if result.get("collectionType", "").lower() == "album":
        score += 10

    if result.get("trackCount"):
        score += 5

    if result.get("country") == "USA":
        score += 3

    return score


def pick_best_release(results: list[dict[str, Any]], artist: str, album: str):
    if not results:
        return None

    return max(results, key=lambda result: score_release(result, artist, album))
