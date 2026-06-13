# audio_metadata_normalizer/itunes_client/trackmap.py

"""Trackmap helpers за iTunes Search API."""

from typing import Any

from audio_metadata_normalizer.mb_client.trackmap import seconds_to_timestamp
from audio_metadata_normalizer.utils.normalize import normalize_track_title


def duration_ms_to_seconds(ms: int | None) -> int | None:
    if not ms or ms <= 0:
        return None
    return round(ms / 1000)


def seconds_to_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    minutes, remaining_seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"


def extract_trackmap(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trackmap = []

    for track in sorted(tracks, key=lambda item: item.get("trackNumber") or 0):
        ms = track.get("trackTimeMillis")
        seconds = duration_ms_to_seconds(ms)
        trackmap.append(
            {
                "title": normalize_track_title(track.get("trackName", "")),
                "duration": seconds_to_duration(seconds),
                "seconds": seconds,
            }
        )

    return trackmap


def compute_chapter_timestamps(trackmap: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chapters = []
    current_time = 0

    for entry in trackmap:
        chapters.append(
            {
                "title": entry["title"],
                "start": seconds_to_timestamp(current_time),
            }
        )

        if entry["seconds"]:
            current_time += entry["seconds"]

    return chapters


def build_trackmap_with_chapters(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = extract_trackmap(tracks)
    chapters = compute_chapter_timestamps(raw)

    return [
        {
            "title": raw_track["title"],
            "duration": raw_track["duration"],
            "start": chapter["start"],
        }
        for raw_track, chapter in zip(raw, chapters)
    ]
