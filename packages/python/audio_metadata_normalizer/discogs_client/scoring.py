# discogs_client/scoring.py

"""
Scoring модул за Discogs.
Избира най-подходящия release от списък с резултати.
Огледален е на mb_client/scoring.py, но адаптиран за Discogs.
"""

from typing import Any, List
from difflib import SequenceMatcher

from audio_metadata_normalizer.utils.normalize import (
    normalize_artist,
    normalize_album,
)


def fuzzy(a: str, b: str) -> float:
    """
    Fuzzy similarity между два низа.
    Използваме SequenceMatcher за стабилност.
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def score_release(result: Any, artist: str, album: str) -> float:
    """
    Изчислява score за даден Discogs release.
    По-висок score = по-добър match.
    """

    score = 0.0

    # Нормализирани входни данни
    artist_n = normalize_artist(artist)
    album_n = normalize_album(album)

    # Discogs release title е във формат: "Artist - Album"
    title = getattr(result, "title", "") or ""
    parts = title.split(" - ", 1)

    release_artist = parts[0] if len(parts) > 1 else ""
    release_album = parts[1] if len(parts) > 1 else title

    # Fuzzy match по artist
    score += fuzzy(artist_n, normalize_artist(release_artist)) * 50

    # Fuzzy match по album
    score += fuzzy(album_n, normalize_album(release_album)) * 50

    # Приоритет за CD издания
    formats = getattr(result, "formats", [])
    for f in formats:
        if f.get("name", "").lower() == "cd":
            score += 20
        if "album" in [d.lower() for d in f.get("descriptions", [])]:
            score += 10

    # Приоритет за Integrity Music / Hosanna! Music
    labels = getattr(result, "labels", [])
    for label in labels:
        lname = str(label).lower()
        if "integrity" in lname:
            score += 25
        if "hosanna" in lname:
            score += 25

    # Приоритет за US/UK издания
    country = getattr(result, "country", "") or ""
    if country.lower() in ("us", "uk"):
        score += 10

    # Приоритет за по-ранни години (оригинални издания)
    year = getattr(result, "year", None)
    if isinstance(year, int):
        score += max(0, 10 - abs(year - 1990) / 5)

    return score


def pick_best_release(results: List[Any], artist: str, album: str) -> Any:
    """
    Избира най-подходящия release от списък с Discogs резултати.
    """

    if not results:
        return None

    scored = []
    for r in results:
        s = score_release(r, artist, album)
        scored.append((s, r))

    # Сортираме по score (низходящо)
    scored.sort(key=lambda x: x[0], reverse=True)

    # Връщаме release с най-висок score
    return scored[0][1]
