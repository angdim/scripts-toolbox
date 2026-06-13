# mb_client/normalize.py

"""
Нормализация на входни и изходни данни за MusicBrainz клиента.
Огледален е на discogs_client/normalize.py, но адаптиран за
MusicBrainz структурата на данните.
"""

import re
import unicodedata


# ------------------------------------------------------------
# Универсална нормализация на текст
# ------------------------------------------------------------

def normalize_string(s: str) -> str:
    """
    Универсална нормализация на текст:
    - Unicode NFC
    - премахване на излишни интервали
    - премахване на точки, тирета, подчертавки
    - конвертиране на multiple separators → space
    - lower-case за по-добро fuzzy matching
    """
    if not s:
        return ""

    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[._\-]+", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip().lower()


# ------------------------------------------------------------
# Нормализация на artist
# ------------------------------------------------------------

def normalize_artist(artist: str) -> str:
    """
    Нормализация на името на изпълнител.
    Премахва:
    - (feat. ...)
    - (featuring ...)
    - (with ...)
    - скоби
    """
    if not artist:
        return ""

    artist = normalize_string(artist)

    artist = re.sub(r"\bfeat(uring)?\b.*", "", artist)
    artist = re.sub(r"\(.*?\)", "", artist)

    return artist.strip()


# ------------------------------------------------------------
# Нормализация на album
# ------------------------------------------------------------

def normalize_album(album: str) -> str:
    """
    Нормализация на името на албума.
    Премахва:
    - ремастери
    - deluxe editions
    - expanded editions
    - anniversary editions
    - скоби
    """
    if not album:
        return ""

    album = normalize_string(album)

    album = re.sub(r"\b(remaster(ed)?|deluxe|expanded|anniversary)\b.*", "", album)
    album = re.sub(r"\(.*?\)", "", album)

    return album.strip()


# ------------------------------------------------------------
# Нормализация на track title
# ------------------------------------------------------------

def normalize_track_title(title: str) -> str:
    """
    Нормализация на заглавия на тракове.
    Премахва:
    - излишни интервали
    - unicode нормализация
    """
    if not title:
        return ""

    title = unicodedata.normalize("NFC", title)
    title = re.sub(r"\s+", " ", title)

    return title.strip()


# ------------------------------------------------------------
# Нормализация на duration
# ------------------------------------------------------------

def normalize_duration_ms(ms: int | None) -> str:
    """
    MusicBrainz дава duration в милисекунди.
    Конвертираме към MM:SS формат.

    Ако няма duration → връща "".
    """
    if not ms or ms <= 0:
        return ""

    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60

    return f"{minutes:02d}:{seconds:02d}"
