# audio_metadata_normalizer/utils/cover_profile.py

"""
Подготовка на обложки за различни compatibility профили.

Стандартният режим `source` оставя подадения файл без промяна. Lexus профилите
създават временен baseline JPEG файл с точен квадратен размер, защото реалният
тест с Lexus RX 450h 2017 показа, че embedded JPEG 300x300 и 500x500 работят,
докато PNG 500x500 не е надежден.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image

COVER_PROFILE_SOURCE = "source"
COVER_PROFILE_LEXUS_JPEG_300 = "lexus-jpeg-300"
COVER_PROFILE_LEXUS_JPEG_500 = "lexus-jpeg-500"

COVER_PROFILE_CHOICES = (
    COVER_PROFILE_SOURCE,
    COVER_PROFILE_LEXUS_JPEG_300,
    COVER_PROFILE_LEXUS_JPEG_500,
)


@dataclass(frozen=True)
class CoverProfile:
    """Нормализирана информация за избрания cover-art профил."""

    name: str
    output_format: str | None = None
    size: int | None = None
    lexus_safe: bool = False


def parse_cover_profile(profile: str | None) -> CoverProfile:
    """Връща структурирана дефиниция за профила или вдига ValueError при грешка."""

    name = profile or COVER_PROFILE_SOURCE
    if name == COVER_PROFILE_SOURCE:
        return CoverProfile(name=name)

    if name == COVER_PROFILE_LEXUS_JPEG_300:
        return CoverProfile(name=name, output_format="jpeg", size=300, lexus_safe=True)

    if name == COVER_PROFILE_LEXUS_JPEG_500:
        return CoverProfile(name=name, output_format="jpeg", size=500, lexus_safe=True)

    raise ValueError(f"Неподдържан cover profile: {profile}")


def build_temp_cover_path(cover_path: str, profile: CoverProfile) -> str:
    """Генерира временен път до обложката в същата директория като оригинала."""

    source = Path(cover_path)
    return str(source.with_name(f".tmp_{profile.name}_{source.stem}.jpg"))


def write_profile_cover(source_path: str, output_path: str, profile: CoverProfile) -> None:
    """Записва обложка според профила; Lexus профилите винаги са JPEG."""

    if not profile.size or profile.output_format != "jpeg":
        raise ValueError(f"Профилът не изисква генериране на JPEG: {profile.name}")

    with Image.open(source_path) as source_image:
        image = source_image.convert("RGB")
        image = image.resize((profile.size, profile.size), Image.Resampling.LANCZOS)
        image.save(output_path, format="JPEG", quality=95, optimize=False, progressive=False)


def ffmpeg_id3v2_version_for_profile(audio_path: str, profile_name: str | None) -> int | None:
    """За MP3 Lexus профилите предпочитаме ID3v2.3 за по-широка съвместимост."""

    profile = parse_cover_profile(profile_name)
    if not profile.lexus_safe:
        return None

    if os.path.splitext(audio_path)[1].lower() != ".mp3":
        return None

    return 3


@contextmanager
def prepared_cover_path(
    cover_path: str | None,
    profile_name: str | None,
    dry_run: bool = False,
) -> Iterator[str | None]:
    """Връща път до обложка, подготвена според профила, и чисти временния файл."""

    if not cover_path:
        yield None
        return

    profile = parse_cover_profile(profile_name)
    if profile.name == COVER_PROFILE_SOURCE:
        yield cover_path
        return

    temp_path = build_temp_cover_path(cover_path, profile)
    print(
        "Подготовка на обложка: "
        f"{os.path.basename(cover_path)} -> {profile.name} ({profile.size}x{profile.size} JPEG)"
    )

    if dry_run:
        yield cover_path
        return

    write_profile_cover(cover_path, temp_path, profile)
    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
