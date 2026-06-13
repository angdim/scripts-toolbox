# audio_metadata_normalizer/utils/dir_rename.py

"""
Планиране и безопасно преименуване на album директории.

Модулът работи с вече извлечени metadata и не зависи от конкретен provider.
"""

from __future__ import annotations

import os
from difflib import SequenceMatcher

from audio_metadata_normalizer.utils.album import parse_album_directory_name
from audio_metadata_normalizer.utils.normalize import (
    normalize_album,
    sanitize_filename_component,
)


DIR_TEMPLATE_CHOICES = (
    "year-title",
    "year-spaced-title",
    "artist-year-title",
    "artist-year-spaced-title",
)


def normalize_dir_year(value) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return text[:4]

    return None


def build_album_dir_name(meta: dict, artist: str, template: str) -> str | None:
    year = normalize_dir_year(meta.get("year"))
    title = sanitize_filename_component(meta.get("title"))
    safe_artist = sanitize_filename_component(artist)

    if not year:
        return None

    if not title:
        return None

    if template == "year-title":
        return f"{year}-{title}"

    if template == "year-spaced-title":
        return f"{year} - {title}"

    if template == "artist-year-title":
        if not safe_artist:
            return None
        return f"{safe_artist} - {year}-{title}"

    if template == "artist-year-spaced-title":
        if not safe_artist:
            return None
        return f"{safe_artist} - {year} - {title}"

    raise ValueError(f"Непознат шаблон за директория: {template}")


def build_album_dir_rename_plan(album_dir: str, meta: dict, artist: str, template: str):
    new_name = build_album_dir_name(meta, artist, template)
    if not new_name:
        print(f"Пропускане: липсва година или име на албум за {album_dir}")
        return None

    parent_dir = os.path.dirname(os.path.abspath(album_dir))
    target_dir = os.path.join(parent_dir, new_name)

    return album_dir, target_dir


def album_title_similarity(left: str | None, right: str | None) -> float:
    left_n = normalize_album(left)
    right_n = normalize_album(right)

    if not left_n or not right_n:
        return 0.0

    return SequenceMatcher(None, left_n, right_n).ratio()


def album_dir_release_is_safe_match(
        album_dir: str,
        expected_album: str,
        meta: dict,
        min_score: float,
) -> bool:
    found_title = meta.get("title")
    score = album_title_similarity(expected_album, found_title)

    if score < min_score:
        print(
            "Пропускане: ниско съвпадение на албум "
            f"'{expected_album}' -> '{found_title}' ({score:.2f})"
        )
        return False

    parsed = parse_album_directory_name(
        os.path.basename(album_dir),
        os.path.basename(os.path.dirname(album_dir)) or None,
    )
    expected_year = parsed.year
    found_year = normalize_dir_year(meta.get("year"))

    if expected_year and found_year and expected_year != found_year:
        print(
            "Пропускане: разминаване в годината "
            f"{expected_year} != {found_year} за '{expected_album}'"
        )
        return False

    return True


def dir_rename_plan_has_conflicts(plan) -> bool:
    source_paths = {os.path.abspath(source) for source, _ in plan}
    target_paths = [os.path.abspath(target) for _, target in plan]

    if len(target_paths) != len(set(target_paths)):
        print("Има повече от една директория със същото целево име.")
        return True

    for source, target in plan:
        source_abs = os.path.abspath(source)
        target_abs = os.path.abspath(target)

        if source_abs == target_abs:
            continue

        if target_abs in source_paths:
            continue

        if os.path.exists(target):
            print(f"Пропускане: целевата директория вече съществува: {target}")
            return True

    return False


def build_temp_dir_rename_path(source_path: str, index: int) -> str:
    parent_dir = os.path.dirname(os.path.abspath(source_path))
    base_name = os.path.basename(source_path)
    return os.path.join(parent_dir, f".tmp_dir_rename_{index}_{base_name}")


def rollback_staged_dir_renames(staged):
    for temp_path, source_path, _ in reversed(staged):
        if os.path.exists(temp_path) and not os.path.exists(source_path):
            os.rename(temp_path, source_path)


def apply_dir_rename_plan(plan, dry_run: bool):
    for source, target in plan:
        print(f"{os.path.basename(source)} -> {os.path.basename(target)}")

    if dry_run:
        return

    if dir_rename_plan_has_conflicts(plan):
        return

    staged: list[tuple[str, str, str]] = []
    unchanged: list[tuple[str, str]] = []

    try:
        for index, (source, target) in enumerate(plan, start=1):
            if os.path.abspath(source) == os.path.abspath(target):
                unchanged.append((source, target))
                continue

            temp_path = build_temp_dir_rename_path(source, index)
            if os.path.exists(temp_path):
                print(f"Пропускане: временната директория вече съществува: {temp_path}")
                rollback_staged_dir_renames(staged)
                return

            os.rename(source, temp_path)
            staged.append((temp_path, source, target))

        for temp_path, _, target in staged:
            os.rename(temp_path, target)
    except Exception:
        rollback_staged_dir_renames(staged)
        raise
