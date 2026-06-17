# audio_metadata_normalizer/utils/cover.py

"""
Помощни функции за локални и изтеглени обложки.

Модулът не зависи от конкретен metadata provider. Работи с общото поле
`cover_urls` от извлечените metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
import re
from urllib.error import HTTPError, URLError
import urllib.request
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

from audio_metadata_normalizer.utils.normalize import sanitize_filename_component


COVER_BASENAMES = ("cover", "folder", "front", "album")
COVER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
DEFAULT_COVER_FILENAME = "cover.jpg"
DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) scripts-toolbox/1.0"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


@dataclass(frozen=True)
class CoverImageInfo:
    """Диагностична информация за локална или remote обложка."""

    label: str
    location: str
    image_format: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    output_path: str | None = None
    error: str | None = None


def safe_cover_basename(value: str | None) -> str:
    """Връща безопасно име за cover файл, базирано на album title."""

    safe = sanitize_filename_component(value or "")
    if not safe:
        return "cover"

    return re.sub(r"\s+", "_", safe)


def normalize_cover_extension(ext: str) -> str:
    """Нормализира cover разширението до по-съвместим файлов suffix."""

    return ".jpg" if ext == ".jpeg" else ext


def iter_local_cover_candidates(album_dir: str):
    for basename in COVER_BASENAMES:
        for ext in COVER_EXTENSIONS:
            yield os.path.join(album_dir, f"{basename}{ext}")


def iter_album_image_files(album_dir: str):
    for name in sorted(os.listdir(album_dir)):
        full = os.path.join(album_dir, name)
        if not os.path.isfile(full):
            continue

        _, ext = os.path.splitext(name)
        if ext.lower() in COVER_EXTENSIONS:
            yield full


def list_local_cover_files(album_dir: str) -> list[str]:
    """Връща локални image файлове, подходящи за cover кандидати, без дублиране."""

    result: list[str] = []
    seen: set[str] = set()

    for candidate in list(iter_local_cover_candidates(album_dir)) + list(iter_album_image_files(album_dir)):
        absolute = os.path.abspath(candidate)
        if absolute in seen or not os.path.isfile(absolute):
            continue
        seen.add(absolute)
        result.append(candidate)

    return result


def find_existing_cover(album_dir: str) -> str | None:
    for candidate in iter_local_cover_candidates(album_dir):
        if os.path.isfile(candidate):
            return candidate

    album_images = list_local_cover_files(album_dir)
    if len(album_images) == 1:
        return album_images[0]

    return None


def cover_extension_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    _, ext = os.path.splitext(path)

    if ext in COVER_EXTENSIONS:
        return ext

    return ".jpg"


def build_cover_output_path(
    album_dir: str,
    url: str | None,
    output_name: str | None = None,
    album_title: str | None = None,
) -> str:
    if output_name:
        if os.path.isabs(output_name):
            return output_name
        return os.path.join(album_dir, output_name)

    basename = safe_cover_basename(album_title)
    ext = normalize_cover_extension(cover_extension_from_url(url or ""))
    return os.path.join(album_dir, f"{basename}{ext}")


def format_size(size_bytes: int | None) -> str:
    """Форматира файлов размер за terminal output."""

    if size_bytes is None:
        return "unknown"

    units = ("B", "KiB", "MiB", "GiB")
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{size_bytes} B"


def inspect_image_bytes(label: str, location: str, data: bytes, output_path: str | None = None) -> CoverImageInfo:
    """Извлича формат и размери от image bytes чрез Pillow."""

    try:
        with Image.open(BytesIO(data)) as image:
            return CoverImageInfo(
                label=label,
                location=location,
                image_format=image.format,
                width=image.width,
                height=image.height,
                size_bytes=len(data),
                output_path=output_path,
            )
    except UnidentifiedImageError as exc:
        return CoverImageInfo(
            label=label,
            location=location,
            size_bytes=len(data),
            output_path=output_path,
            error=f"неразпознат image формат: {exc}",
        )


def inspect_image_file(path: str, label: str | None = None) -> CoverImageInfo:
    """Извлича формат, размери и файлов размер от локален image файл."""

    try:
        with open(path, "rb") as image_file:
            return inspect_image_bytes(label or os.path.basename(path), path, image_file.read())
    except OSError as exc:
        return CoverImageInfo(label=label or os.path.basename(path), location=path, error=str(exc))


def fetch_remote_cover_bytes(url: str) -> bytes | None:
    """Изтегля remote image bytes в памет, без запис на диск."""

    request = urllib.request.Request(url, headers=DOWNLOAD_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except HTTPError as exc:
        print(f"Грешка при проверка на remote обложка: HTTP {exc.code} {exc.reason}")
        return None
    except URLError as exc:
        print(f"Грешка при проверка на remote обложка: {exc.reason}")
        return None


def inspect_remote_cover(url: str, index: int, output_path: str) -> CoverImageInfo:
    """Проверява remote cover кандидат и връща диагностична информация."""

    data = fetch_remote_cover_bytes(url)
    label = f"remote #{index}"
    if data is None:
        return CoverImageInfo(label=label, location=url, output_path=output_path, error="неуспешна проверка")

    return inspect_image_bytes(label, url, data, output_path=output_path)


def print_cover_info(info: CoverImageInfo) -> None:
    """Извежда cover diagnostic ред в терминала."""

    print(f"- {info.label}: {info.location}")
    if info.error:
        print(f"  грешка: {info.error}")
        return

    dimensions = (
        f"{info.width}x{info.height}px"
        if info.width is not None and info.height is not None
        else "unknown"
    )
    print(f"  формат: {info.image_format or 'unknown'}")
    print(f"  размери: {dimensions}")
    print(f"  файл: {format_size(info.size_bytes)}")
    if info.output_path:
        print(f"  ще се запише като: {info.output_path}")


def print_local_cover_report(album_dir: str) -> None:
    """Показва информация за всички локални cover image кандидати."""

    local_covers = list_local_cover_files(album_dir)
    if not local_covers:
        print("Локални обложки: няма намерени image файлове.")
        return

    print("Локални обложки:")
    for index, path in enumerate(local_covers, start=1):
        print_cover_info(inspect_image_file(path, label=f"local #{index}"))


def print_remote_cover_report(album_dir: str, meta: dict) -> None:
    """Показва информация за всички remote cover кандидати от metadata."""

    urls = meta.get("cover_urls") or []
    if not urls:
        print("Remote обложки: няма URL кандидати в metadata.")
        return

    print("Remote обложки:")
    for index, url in enumerate(urls, start=1):
        output_path = build_cover_output_path(album_dir, url, album_title=meta.get("title"))
        print_cover_info(inspect_remote_cover(url, index, output_path))


def download_cover(url: str, output_path: str, dry_run: bool = False):
    print(f"Изтегляне на обложка: {url}")
    print(f"Запис като: {output_path}")

    if dry_run:
        return

    request = urllib.request.Request(url, headers=DOWNLOAD_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    except HTTPError as exc:
        print(f"Грешка при изтегляне на обложка: HTTP {exc.code} {exc.reason}")
        print("Ако URL е от Discogs/CDN, опитай по-късно или свали обложката ръчно и я подай с -C.")
        return None
    except URLError as exc:
        print(f"Грешка при изтегляне на обложка: {exc.reason}")
        print("Провери интернет връзката, DNS/VPN настройките или свали обложката ръчно и я подай с -C.")
        return None

    if not data:
        raise RuntimeError("Изтеглената обложка е празна.")

    with open(output_path, "wb") as cover_file:
        cover_file.write(data)

    return output_path


def select_cover_url(meta: dict, cover_index: int = 1) -> str | None:
    urls = meta.get("cover_urls") or []
    if not urls:
        return None

    if cover_index < 1 or cover_index > len(urls):
        print(f"Невалиден cover index: {cover_index}. Налични кандидати: 1-{len(urls)}.")
        return None

    return urls[cover_index - 1]


def ensure_cover_download(
    album_dir: str,
    meta: dict,
    force: bool = False,
    dry_run: bool = False,
    cover_index: int = 1,
):
    if dry_run:
        print_local_cover_report(album_dir)
        print_remote_cover_report(album_dir, meta)
        if len(meta.get("cover_urls") or []) > 1:
            print("За избор при реално изтегляне използвай: --cover-index N")
        return None

    existing = find_existing_cover(album_dir)
    if existing and not force:
        print(f"Има налична обложка: {existing}")
        return existing

    url = select_cover_url(meta, cover_index)
    if not url:
        print("Няма URL за обложка в metadata.")
        return None

    output_path = build_cover_output_path(album_dir, url, album_title=meta.get("title"))
    if os.path.exists(output_path) and not force:
        print(f"Има налична обложка: {output_path}")
        return output_path

    return download_cover(url, output_path, dry_run=dry_run)


def resolve_cover_path(album_dir: str, explicit_cover: str | None, auto_cover: bool) -> str | None:
    if explicit_cover:
        if os.path.isabs(explicit_cover):
            return explicit_cover
        return os.path.abspath(os.path.join(album_dir, explicit_cover))

    if not auto_cover:
        return None

    cover_path = find_existing_cover(album_dir)
    if not cover_path:
        print("Няма локална обложка за автоматично вграждане.")
        return None

    print(f"Автоматично използване на обложка: {cover_path}")
    return cover_path
