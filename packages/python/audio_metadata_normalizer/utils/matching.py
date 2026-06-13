# audio_metadata_normalizer/utils/matching.py

"""
Обща логика за сравнение между локални аудио файлове и тракове от база данни.
"""

import os
from difflib import SequenceMatcher

from audio_metadata_normalizer.utils.normalize import (
    normalize_track_filename,
    normalize_track_title,
)


def similarity_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0

    return SequenceMatcher(None, left, right).ratio()


def score_file_track(file_path: str, track: dict) -> float:
    local_name = normalize_track_filename(os.path.basename(file_path))
    track_title = normalize_track_title(track.get("title", ""))
    return similarity_score(local_name, normalize_track_filename(track_title))


def match_files_to_tracks(files, trackmap, min_score: float = 0.55):
    if len(files) != len(trackmap):
        return None

    remaining_files = list(files)
    matched: list[tuple[str, dict, float]] = []

    for track in trackmap:
        scored = [
            (score_file_track(file_path, track), file_path)
            for file_path in remaining_files
        ]
        scored.sort(key=lambda item: item[0], reverse=True)

        best_score, best_file = scored[0]
        if best_score < min_score:
            print(
                "Ниско съвпадение: "
                f"{os.path.basename(best_file)} -> {track.get('title', '')} "
                f"({best_score:.2f})"
            )
            print("Оставащи файлове:")
            for file_path in remaining_files:
                print(f"  - {os.path.basename(file_path)}")
            print("Оставащи тракове:")
            for pending_track in trackmap[len(matched):]:
                print(f"  - {pending_track.get('title', '')}")
            return None

        matched.append((best_file, track, best_score))
        remaining_files.remove(best_file)

    return matched
