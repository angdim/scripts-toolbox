# discogs_client/normalize.py

"""
Нормализация на входни и изходни данни за Discogs клиента.
Този модул е огледален на mb_client/normalize.py, но адаптиран
за Discogs структурата на данните.
"""

import re
import unicodedata


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

    # Unicode нормализация
    s = unicodedata.normalize("NFC", s)

    # Замяна на разделители с интервал
    s = re.sub(r"[._\-]+", " ", s)

    # Премахване на двойни интервали
    s = re.sub(r"\s+", " ", s)

    return s.strip().lower()


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

    # Премахване на featuring
    artist = re.sub(r"\bfeat(uring)?\b.*", "", artist)

    # Премахване на скоби
    artist = re.sub(r"\(.*?\)", "", artist)

    return artist.strip()


def normalize_album(album: str) -> str:
    """
    Нормализация на името на албума.
    Премахва:
    - ремастери
    - deluxe editions
    - bonus tracks
    - скоби
    """
    if not album:
        return ""

    album = normalize_string(album)

    # Премахване на ремастери
    album = re.sub(r"\b(remaster(ed)?|deluxe|expanded|anniversary)\b.*", "", album)

    # Премахване на скоби
    album = re.sub(r"\(.*?\)", "", album)

    return album.strip()


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


def normalize_duration(duration: str) -> str:
    """
    Нормализация на Discogs duration формат.
    Discogs може да върне:
        "4:12"
        "03:09"
        "1:02"
        "4.12"
        "4-12"
    Ние го конвертираме към MM:SS.
    """
    if not duration:
        return ""

    # Замяна на разделители
    duration = duration.replace(".", ":").replace("-", ":")

    # Извличане на минути и секунди
    m = re.match(r"(\d+):(\d+)", duration)
    if not m:
        return ""

    minutes = int(m.group(1))
    seconds = int(m.group(2))

    return f"{minutes:02d}:{seconds:02d}"
