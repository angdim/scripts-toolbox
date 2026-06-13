# audio_metadata_normalizer/utils/tagging.py

"""
Обща логика за изграждане и запис на аудио метаданни.

Модулът не зависи от CLI и може да се използва от различни интерфейси.
"""

import os

from audio_metadata_normalizer.utils.ffmpeg import ffmpeg_tag_file


def build_track_tags(meta: dict, track: dict, artist: str, track_number: int, total_tracks: int):
    return {
        "title": track["title"],
        "album": meta.get("title"),
        "artist": artist,
        "album_artist": artist,
        "track": f"{track_number}/{total_tracks}",
        "date": meta.get("year"),
        "genre": ", ".join(meta.get("genres", []) or []),
        "comment": f"{meta.get('label') or ''} {meta.get('catno') or ''}".strip()
    }


def build_temp_tag_path(path: str, track_number: int) -> str:
    dir_name = os.path.dirname(path)
    base_name = os.path.basename(path)
    return os.path.join(dir_name, f".tmp_tag_{track_number}_{base_name}")


def build_album_tags(meta: dict, artist: str):
    return {
        "title": meta.get("title"),
        "album": meta.get("title"),
        "artist": artist,
        "album_artist": artist,
        "date": meta.get("year"),
        "genre": ", ".join(meta.get("genres", []) or []),
        "comment": f"{meta.get('label') or ''} {meta.get('catno') or ''}".strip()
    }


def tag_audio_file(path: str, tags: dict, cover_path: str | None, dry_run: bool):
    tmp_out = build_temp_tag_path(path, 0)

    print(f"Тагване: {os.path.basename(path)}")
    if dry_run:
        return

    ffmpeg_tag_file(path, tmp_out, tags, cover_path)
    os.replace(tmp_out, path)


def tag_matched_files(meta: dict, matched, artist: str, cover_path: str | None, dry_run: bool):
    total_tracks = len(matched)

    for idx, (path, track, score) in enumerate(matched, start=1):
        tmp_out = build_temp_tag_path(path, idx)
        tags = build_track_tags(meta, track, artist, idx, total_tracks)

        print(f"Тагване: {os.path.basename(path)} ({score:.2f})")
        if dry_run:
            continue

        ffmpeg_tag_file(path, tmp_out, tags, cover_path)
        os.replace(tmp_out, path)
