# mb_client/scoring.py

"""
Scoring модул за MusicBrainz.
Избира най-подходящия release от списък с резултати.
Огледален е на discogs_client/scoring.py, но адаптиран за MusicBrainz.
"""

from typing import Any, List
from difflib import SequenceMatcher

from audio_metadata_normalizer.utils.normalize import (
    normalize_artist,
    normalize_album,
)


# ------------------------------------------------------------
# Fuzzy matching
# ------------------------------------------------------------

def fuzzy(a: str, b: str) -> float:
    """
    Fuzzy similarity между два низа.
    Използваме SequenceMatcher за стабилност.
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ------------------------------------------------------------
# Scoring на release
# ------------------------------------------------------------

def score_release(result: Any, artist: str, album: str) -> float:
    """
    Изчислява score за даден MusicBrainz release.
    По-висок score = по-добър match.
    """

    score = 0.0

    # Нормализирани входни данни
    artist_n = normalize_artist(artist)
    album_n = normalize_album(album)

    # --------------------------------------------------------
    # 1) Artist match
    # --------------------------------------------------------
    release_artist = ""
    if "artist-credit" in result and result["artist-credit"]:
        release_artist = result["artist-credit"][0]["artist"]["name"]

    score += fuzzy(artist_n, normalize_artist(release_artist)) * 50

    # --------------------------------------------------------
    # 2) Album title match
    # --------------------------------------------------------
    release_title = result.get("title", "")
    score += fuzzy(album_n, normalize_album(release_title)) * 50

    # --------------------------------------------------------
    # 3) Приоритет за CD издания
    # --------------------------------------------------------
    if "medium-list" in result:
        for m in result["medium-list"]:
            if m.get("format", "").lower() == "cd":
                score += 20

    # --------------------------------------------------------
    # 4) Приоритет за оригинални години (ако има date)
    # --------------------------------------------------------
    date = result.get("date")
    if date and len(date) >= 4:
        try:
            year = int(date[:4])
            score += max(0, 10 - abs(year - 1990) / 5)
        except ValueError:
            pass

    # --------------------------------------------------------
    # 5) Приоритет за US/UK издания
    # --------------------------------------------------------
    country = result.get("country", "")
    if country.lower() in ("us", "uk"):
        score += 10

    # --------------------------------------------------------
    # 6) Приоритет за release-group primary type = Album
    # --------------------------------------------------------
    if "release-group" in result:
        rg = result["release-group"]
        if rg.get("primary-type", "").lower() == "album":
            score += 15

    return score


# ------------------------------------------------------------
# Избор на най-добър release
# ------------------------------------------------------------

def pick_best_release(results: List[Any], artist: str, album: str) -> Any:
    """
    Избира най-подходящия release от списък с MusicBrainz резултати.
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
