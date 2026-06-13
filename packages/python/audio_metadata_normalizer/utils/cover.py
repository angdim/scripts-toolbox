# audio_metadata_normalizer/utils/cover.py

"""
Помощни функции за локални и изтеглени обложки.

Модулът не зависи от конкретен metadata provider. Работи с общото поле
`cover_urls` от извлечените metadata.
"""

from __future__ import annotations

import os
import urllib.request
from urllib.parse import urlparse


COVER_BASENAMES = ("cover", "folder", "front", "album")
COVER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
DEFAULT_COVER_FILENAME = "cover.jpg"


def iter_local_cover_candidates(album_dir: str):
    for basename in COVER_BASENAMES:
        for ext in COVER_EXTENSIONS:
            yield os.path.join(album_dir, f"{basename}{ext}")


def find_existing_cover(album_dir: str) -> str | None:
    for candidate in iter_local_cover_candidates(album_dir):
        if os.path.isfile(candidate):
            return candidate

    return None


def cover_extension_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    _, ext = os.path.splitext(path)

    if ext in COVER_EXTENSIONS:
        return ext

    return ".jpg"


def select_cover_url(meta: dict) -> str | None:
    urls = meta.get("cover_urls") or []
    if not urls:
        return None

    return urls[0]


def build_cover_output_path(album_dir: str, url: str | None, output_name: str | None = None) -> str:
    if output_name:
        if os.path.isabs(output_name):
            return output_name
        return os.path.join(album_dir, output_name)

    ext = cover_extension_from_url(url or "")
    if ext in {".jpeg", ".webp", ".png"}:
        return os.path.join(album_dir, f"cover{ext}")

    return os.path.join(album_dir, DEFAULT_COVER_FILENAME)


def download_cover(url: str, output_path: str, dry_run: bool = False):
    print(f"Изтегляне на обложка: {url}")
    print(f"Запис като: {output_path}")

    if dry_run:
        return

    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read()

    if not data:
        raise RuntimeError("Изтеглената обложка е празна.")

    with open(output_path, "wb") as cover_file:
        cover_file.write(data)


def ensure_cover_download(album_dir: str, meta: dict, force: bool = False, dry_run: bool = False):
    existing = find_existing_cover(album_dir)
    if existing and not force:
        print(f"Има налична обложка: {existing}")
        return existing

    url = select_cover_url(meta)
    if not url:
        print("Няма URL за обложка в metadata.")
        return None

    output_path = build_cover_output_path(album_dir, url)
    if os.path.exists(output_path) and not force:
        print(f"Има налична обложка: {output_path}")
        return output_path

    download_cover(url, output_path, dry_run=dry_run)
    return output_path


def resolve_cover_path(album_dir: str, explicit_cover: str | None, auto_cover: bool) -> str | None:
    if explicit_cover:
        return explicit_cover

    if not auto_cover:
        return None

    cover_path = find_existing_cover(album_dir)
    if not cover_path:
        print("Няма локална обложка за автоматично вграждане.")
        return None

    print(f"Автоматично използване на обложка: {cover_path}")
    return cover_path
