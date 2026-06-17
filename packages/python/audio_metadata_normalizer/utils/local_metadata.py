# audio_metadata_normalizer/utils/local_metadata.py

"""
Локално изграждане на track metadata от имената на файловете.

Този модул се използва, когато албумът липсва във външните metadata бази,
но файловете вече са коректно номерирани и именувани.
"""

from __future__ import annotations

import os

from audio_metadata_normalizer.utils.files import iter_audio_files
from audio_metadata_normalizer.utils.normalize import (
    extract_track_number,
    normalize_local_track_name,
)


def build_local_album_metadata(album: str) -> dict:
    """Създава минимални album-level metadata от подаденото име на албум."""

    return {
        "title": album,
        "year": None,
        "genres": [],
        "label": None,
        "catno": None,
    }


def build_local_trackmap(album_dir: str) -> list[dict]:
    """Извлича trackmap от аудио файловете в директорията."""

    trackmap = []
    for index, path in enumerate(iter_audio_files(album_dir), start=1):
        title = normalize_local_track_name(path) or os.path.splitext(os.path.basename(path))[0]
        trackmap.append(
            {
                "title": title,
                "source_track_number": extract_track_number(path) or index,
            }
        )

    return trackmap


def build_local_matched_tracks(album_dir: str) -> list[tuple[str, dict, float]]:
    """Връща matched структура, съвместима с rename/tag workflow-а."""

    result = []
    for path, track in zip(iter_audio_files(album_dir), build_local_trackmap(album_dir)):
        result.append((path, track, 1.0))

    return result
