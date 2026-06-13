# audio_metadata_normalizer/utils/album.py

"""
Общи helper-и за разпознаване на изпълнител/албум и избор на албум директории.

Модулът не зависи от Discogs, MusicBrainz или argparse.
"""

import os
import re
from dataclasses import dataclass

from audio_metadata_normalizer.utils.files import (
    iter_album_dirs,
    iter_audio_files,
)
from audio_metadata_normalizer.utils.normalize import (
    build_track_filename,
    normalize_album,
    normalize_artist,
)


_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
_LEADING_YEAR_PREFIX_RE = re.compile(r"^\s*((?:19|20)\d{2})\s*[-_.]\s*(.+?)\s*$")
_BRACKETED_YEAR_RE = re.compile(r"\s*[\[\(]\s*((?:19|20)\d{2})\s*[\]\)]\s*")
_BRACKETED_NOISE_RE = re.compile(
    r"\s*[\[\(]\s*(?:\d{2,4}\s*kbps|vbr|cbr|mp3|flac|m4a|aac|opus|ogg|wav|lossless|web[-\s]?dl|cd[-\s]?rip|vinyl)\s*[\]\)]\s*",
    re.IGNORECASE,
)
_DASH_SEPARATOR_RE = re.compile(r"\s+(?:-|–|—)\s+")
_MULTI_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class AlbumDirectoryParts:
    artist: str | None
    album: str | None
    year: str | None = None


def make_filename(
        track_number: int,
        title: str,
        ext: str,
        total_tracks: int | None = None
) -> str:
    return build_track_filename(track_number, title, ext, total_tracks)


def _clean_name_part(value: str | None) -> str | None:
    if not value:
        return None

    text = _BRACKETED_NOISE_RE.sub(" ", value)
    text = re.sub(r"[\[\(]\s*[\]\)]", " ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = text.strip(" ._-")
    return text or None


def _strip_bracketed_typed_data(value: str) -> tuple[str, str | None]:
    year = None

    def replace_year(match):
        nonlocal year
        year = year or match.group(1)
        return " "

    text = _BRACKETED_YEAR_RE.sub(replace_year, value)
    text = _BRACKETED_NOISE_RE.sub(" ", text)
    return text, year


def _is_year_token(value: str | None) -> bool:
    return bool(value and _YEAR_RE.fullmatch(value.strip()))


def _split_album_dir_name(value: str) -> list[str]:
    return [
        part
        for part in (_clean_name_part(part) for part in _DASH_SEPARATOR_RE.split(value))
        if part
    ]


def _same_artist(left: str | None, right: str | None) -> bool:
    return bool(left and right and normalize_artist(left) == normalize_artist(right))


def parse_album_directory_name(dir_name: str, parent_artist: str | None = None) -> AlbumDirectoryParts:
    text, year = _strip_bracketed_typed_data(dir_name)
    parts = _split_album_dir_name(text)

    if not parts:
        return AlbumDirectoryParts(parent_artist or None, None, year)

    year_parts = [part for part in parts if _is_year_token(part)]
    if year_parts and not year:
        year = year_parts[0]

    if len(parts) >= 3:
        typed_parts = [part for part in parts if not _is_year_token(part)]
        if len(typed_parts) >= 2:
            return AlbumDirectoryParts(
                _clean_name_part(typed_parts[0]),
                _clean_name_part(" - ".join(typed_parts[1:])),
                year,
            )

    if len(parts) == 2:
        first, second = parts

        if _same_artist(first, parent_artist):
            prefixed = _LEADING_YEAR_PREFIX_RE.match(second)
            if prefixed:
                year = year or prefixed.group(1)
                second = prefixed.group(2)
            return AlbumDirectoryParts(parent_artist or first, _clean_name_part(second), year)

        if _is_year_token(first) and parent_artist:
            return AlbumDirectoryParts(parent_artist, _clean_name_part(second), year)

        if _is_year_token(second) and parent_artist:
            return AlbumDirectoryParts(parent_artist, _clean_name_part(first), year)

        return AlbumDirectoryParts(_clean_name_part(first), _clean_name_part(second), year)

    only = parts[0]
    prefixed = _LEADING_YEAR_PREFIX_RE.match(only)
    if prefixed and parent_artist:
        year = year or prefixed.group(1)
        return AlbumDirectoryParts(parent_artist, _clean_name_part(prefixed.group(2)), year)

    if _is_year_token(only):
        return AlbumDirectoryParts(parent_artist or None, only, year)

    return AlbumDirectoryParts(parent_artist or None, _clean_name_part(only), year)


def guess_artist_album_from_dir(dir_path: str):
    album_dir = os.path.abspath(dir_path)
    raw_album = os.path.basename(album_dir).strip()
    parent_artist = os.path.basename(os.path.dirname(album_dir)).strip() or None

    parts = parse_album_directory_name(raw_album, parent_artist)

    return parts.artist, parts.album


def resolve_artist_album(
        album_dir: str,
        artist_override: str | None,
        album_override: str | None
):
    guessed_artist, guessed_album = guess_artist_album_from_dir(album_dir)
    return artist_override or guessed_artist, album_override or guessed_album


def validate_track_count(files, trackmap) -> bool:
    if len(files) == len(trackmap):
        return True

    print(f"БРОЙ ФАЙЛОВЕ ({len(files)}) != БРОЙ ТРАКОВЕ ({len(trackmap)})")
    return False


def filter_album_dirs(album_dirs, album_only):
    if not album_only:
        return list(album_dirs)

    wanted = {normalize_album(album_name) for album_name in album_only}
    result = []

    for album_dir in album_dirs:
        _, parsed_album = guess_artist_album_from_dir(album_dir)
        candidates = {
            normalize_album(os.path.basename(album_dir)),
            normalize_album(parsed_album),
        }

        if candidates & wanted:
            result.append(album_dir)

    return result


def resolve_album_dirs(target_dir: str, album_only=None):
    if not os.path.isdir(target_dir):
        print(f"Директорията не съществува: {target_dir}")
        return []

    album_dirs = filter_album_dirs(iter_album_dirs(target_dir), album_only or [])

    if not album_dirs:
        print("Няма намерени директории с аудио файлове за обработка.")

    return album_dirs


def is_multi_file_album(album_dir: str) -> bool:
    return len(list(iter_audio_files(album_dir))) > 1


def ensure_multi_file_album(album_dir: str, operation_label: str) -> bool:
    if is_multi_file_album(album_dir):
        return True

    print(
        f"Пропускане: {operation_label} изисква multi-file албум "
        f"с повече от един аудио файл: {album_dir}"
    )
    return False
