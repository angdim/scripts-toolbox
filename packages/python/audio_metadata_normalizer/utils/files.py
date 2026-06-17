# audio_metadata_normalizer/utils/files.py

"""
Общи файлови операции за албуми и аудио файлове.

Тук стоят само операции по откриване на файлове, директории и бекъп.
Модулът не зависи от Discogs, MusicBrainz или CLI парсъра.
"""

import os
import shutil
from glob import glob

from audio_metadata_normalizer.utils.normalize import natural_sort_key


AUDIO_EXT = {".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus"}
IGNORED_DIR_NAMES = {"_backup", ".backup", ".git", "__pycache__"}


def iter_audio_files(dir_path: str):
    for name in sorted(os.listdir(dir_path), key=natural_sort_key):
        full = os.path.join(dir_path, name)
        if not os.path.isfile(full):
            continue

        _, ext = os.path.splitext(name)
        if ext.lower() in AUDIO_EXT:
            yield full


def has_audio_files(dir_path: str) -> bool:
    return any(iter_audio_files(dir_path))


def is_single_file_album(dir_path: str) -> bool:
    return len(list(iter_audio_files(dir_path))) == 1


def get_single_audio_file(album_dir: str) -> str | None:
    files = list(iter_audio_files(album_dir))
    if len(files) == 1:
        return files[0]

    print(f"Пропускане: директорията трябва да съдържа точно един аудио файл: {album_dir}")
    return None


def is_audio_file(file_path: str) -> bool:
    if not os.path.isfile(file_path):
        return False

    _, ext = os.path.splitext(file_path)
    return ext.lower() in AUDIO_EXT


def resolve_sfa_audio_files(sfa_files=None, sfa_globs=None) -> list[str]:
    """Разрешава explicit SFA входове от файлове и glob шаблони."""

    candidates: list[str] = []

    for file_path in sfa_files or []:
        candidates.append(file_path)

    for pattern in sfa_globs or []:
        candidates.extend(glob(pattern))

    result: list[str] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=natural_sort_key):
        absolute = os.path.abspath(candidate)
        if absolute in seen:
            continue
        seen.add(absolute)

        if not is_audio_file(absolute):
            print(f"Пропускане: не е поддържан аудио файл: {candidate}")
            continue

        result.append(absolute)

    if candidates and not result:
        print("Няма валидни SFA аудио файлове за обработка.")

    return result


def iter_album_dirs(target_dir: str):
    if has_audio_files(target_dir):
        yield os.path.abspath(target_dir)
        return

    for name in sorted(os.listdir(target_dir), key=natural_sort_key):
        if name in IGNORED_DIR_NAMES:
            continue

        full = os.path.join(target_dir, name)
        if os.path.isdir(full) and has_audio_files(full):
            yield os.path.abspath(full)


def resolve_backup_dir(target_dir: str, user_backup: str | None) -> str:
    if user_backup:
        return user_backup

    return os.path.join(target_dir, "_backup")


def should_create_backup(no_backup: bool, dry_run: bool) -> bool:
    return not no_backup and not dry_run


def ensure_backup(dir_path: str, backup_dir: str):
    os.makedirs(backup_dir, exist_ok=True)

    for file_path in iter_audio_files(dir_path):
        shutil.copy2(file_path, backup_dir)


def ensure_file_backup(file_path: str, backup_dir: str):
    os.makedirs(backup_dir, exist_ok=True)
    shutil.copy2(file_path, backup_dir)
