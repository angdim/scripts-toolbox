# discogs_client/trackmap.py

"""
Trackmap модул за Discogs.
Извлича траклист + durations от Discogs release и ги конвертира
в таймкодове, подходящи за OGM/FFmpeg chapters.
"""

from typing import List, Dict, Any, Optional
from audio_metadata_normalizer.utils.normalize import normalize_track_title, normalize_duration


def duration_to_seconds(duration: str) -> Optional[int]:
    """
    Конвертира MM:SS → секунди.
    Ако duration е празно или невалидно → връща None.
    """
    if not duration:
        return None

    duration = normalize_duration(duration)
    if not duration:
        return None

    try:
        minutes, seconds = duration.split(":")
        return int(minutes) * 60 + int(seconds)
    except Exception:
        return None


def seconds_to_timestamp(sec: int) -> str:
    """
    Конвертира секунди → HH:MM:SS.mmm (OGM chapter формат).
    """
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    seconds = sec % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.000"


def extract_trackmap(release: Any) -> List[Dict[str, Any]]:
    """
    Извлича траклист от Discogs release и връща структура:

    [
        {"title": "Sing Out", "duration": "07:19", "seconds": 439},
        {"title": "Joyfully, Joyfully", "duration": "03:09", "seconds": 189},
        ...
    ]
    """

    trackmap = []

    for t in release.tracklist:
        title = normalize_track_title(t.title)
        duration = normalize_duration(t.duration)
        seconds = duration_to_seconds(duration)

        trackmap.append({
            "title": title,
            "duration": duration,
            "seconds": seconds
        })

    return trackmap


def compute_chapter_timestamps(trackmap: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Взема trackmap със seconds и генерира:

    [
        {"title": "...", "start": "00:00:00.000"},
        {"title": "...", "start": "00:07:19.000"},
        ...
    ]
    """

    chapters = []
    current_time = 0

    for entry in trackmap:
        title = entry["title"]
        sec = entry["seconds"]

        chapters.append({
            "title": title,
            "start": seconds_to_timestamp(current_time)
        })

        if sec:
            current_time += sec

    return chapters


def build_trackmap_with_chapters(release: Any) -> List[Dict[str, Any]]:
    """
    Комбинирана функция:
    - извлича tracklist + durations
    - конвертира durations → seconds
    - генерира chapter timestamps

    Връща:

    [
        {"title": "...", "duration": "07:19", "start": "00:00:00.000"},
        {"title": "...", "duration": "03:09", "start": "00:07:19.000"},
        ...
    ]
    """

    raw = extract_trackmap(release)
    chapters = compute_chapter_timestamps(raw)

    # комбинираме duration + start
    combined = []
    for r, c in zip(raw, chapters):
        combined.append({
            "title": r["title"],
            "duration": r["duration"],
            "start": c["start"]
        })

    return combined
