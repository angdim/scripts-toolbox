# audio_metadata_normalizer/utils/rename.py

"""
Обща логика за планиране и безопасно двуфазно преименуване на аудио файлове.
"""

import os

from audio_metadata_normalizer.utils.normalize import build_track_filename


def build_rename_plan(matched, total_tracks: int):
    plan = []

    for idx, (path, track, score) in enumerate(matched, start=1):
        dir_name = os.path.dirname(path)
        _, ext = os.path.splitext(path)
        new_name = build_track_filename(idx, track["title"], ext, total_tracks)
        new_path = os.path.join(dir_name, new_name)
        plan.append((path, new_path, track, score))

    return plan


def rename_plan_has_conflicts(plan) -> bool:
    source_paths = {
        os.path.abspath(source_path)
        for source_path, _, _, _ in plan
    }
    target_paths = [
        os.path.abspath(target_path)
        for _, target_path, _, _ in plan
    ]

    if len(target_paths) != len(set(target_paths)):
        print("Има повече от един файл със същото целево име.")
        return True

    for _, target_path, _, _ in plan:
        target_abs = os.path.abspath(target_path)

        if target_abs in source_paths:
            continue

        if os.path.exists(target_path):
            print(f"Пропускане: целевият файл вече съществува: {target_path}")
            return True

    return False


def build_temp_rename_path(source_path: str, index: int) -> str:
    dir_name = os.path.dirname(source_path)
    base_name = os.path.basename(source_path)
    return os.path.join(dir_name, f".tmp_rename_{index}_{base_name}")


def rollback_staged_renames(staged):
    for temp_path, source_path, _, _, _ in reversed(staged):
        if os.path.exists(temp_path) and not os.path.exists(source_path):
            os.rename(temp_path, source_path)


def finalize_staged_renames(staged):
    for temp_path, _, target_path, _, _ in staged:
        os.rename(temp_path, target_path)


def build_renamed_matches(staged, unchanged):
    return [
        (target_path, track, score)
        for _, _, target_path, track, score in staged
    ] + [
        (source_path, track, score)
        for source_path, _, track, score in unchanged
    ]


def apply_rename_plan(plan, dry_run: bool):
    renamed = []

    for source_path, target_path, track, score in plan:
        print(
            f"{os.path.basename(source_path)} -> {os.path.basename(target_path)} "
            f"({score:.2f})"
        )
        renamed.append((target_path, track, score))

    if dry_run:
        return renamed

    if rename_plan_has_conflicts(plan):
        return []

    staged: list[tuple] = []
    unchanged: list[tuple] = []

    try:
        for idx, (source_path, target_path, track, score) in enumerate(plan, start=1):
            if os.path.abspath(source_path) == os.path.abspath(target_path):
                unchanged.append((source_path, target_path, track, score))
                continue

            temp_path = build_temp_rename_path(source_path, idx)
            if os.path.exists(temp_path):
                print(f"Пропускане: временният файл вече съществува: {temp_path}")
                rollback_staged_renames(staged)
                return []

            os.rename(source_path, temp_path)
            staged.append((temp_path, source_path, target_path, track, score))

        finalize_staged_renames(staged)
    except Exception:
        rollback_staged_renames(staged)
        raise

    return build_renamed_matches(staged, unchanged)
