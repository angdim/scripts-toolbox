"""Shared normalization helpers used by both metadata providers and albumtool.

This module is intentionally source-agnostic:
- text normalization for matching
- filename cleanup for local files and remote titles
- duration conversion
- deterministic filename generation
- natural sorting helpers

Discogs and MusicBrainz adapters will import from here instead of keeping
separate copies of the same logic.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "normalize",
    "normalize_string",
    "normalize_artist",
    "normalize_album",
    "normalize_track_title",
    "normalize_duration",
    "normalize_duration_ms",
    "duration_to_seconds",
    "strip_leading_track_prefix",
    "strip_ytdlp_noise",
    "normalize_local_track_name",
    "normalize_track_filename",
    "sanitize_filename_component",
    "build_track_filename",
    "track_number_width",
    "extract_track_number",
    "natural_sort_key",
]

_MULTI_SPACE_RE = re.compile(r"\s+")
_SEPARATOR_RE = re.compile(r"[._]+")
_INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')
_LEADING_TRACK_PREFIX_RE = re.compile(
    r"^\s*(?:track\s*)?(?P<num>\d{1,3})(?:\s*[-._)\]]+\s*|\s+)"
)
_TRAILING_BRACKETED_NOISE_RE = re.compile(
    r"\s*[\[\(]\s*(?:official(?:\s+(?:audio|video|music\s+video))?|audio|video|lyrics?|lyric\s+video|topic|visualizer|hd|hq|4k|mv)\b.*?[\]\)]\s*$",
    re.IGNORECASE,
)
_TRAILING_DASH_NOISE_RE = re.compile(
    r"\s*-\s*(?:official(?:\s+(?:audio|video|music\s+video))?|audio|video|lyrics?|lyric\s+video|topic|visualizer|hd|hq|4k|mv)\b.*$",
    re.IGNORECASE,
)
_PROVIDED_TO_YOUTUBE_RE = re.compile(
    r"\s*-\s*provided to youtube by.*$",
    re.IGNORECASE,
)
_ALBUM_BRACKETED_NOISE_RE = re.compile(
    r"\s*[\[\(]\s*(?:(?:19|20)\d{2}|\d{2,4}\s*kbps|vbr|cbr|mp3|flac|m4a|aac|opus|ogg|wav|lossless|web[-\s]?dl|cd[-\s]?rip|vinyl)\s*[\]\)]\s*",
    re.IGNORECASE,
)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _path_stem(value: Any) -> str:
    text = _coerce_text(value).replace("\\", "/")
    path = Path(text)
    suffix = path.suffix

    if suffix and re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix):
        return path.stem

    return path.name


def normalize_string(value: Any) -> str:
    text = _coerce_text(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00A0", " ").replace("\u200B", "")
    text = _SEPARATOR_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip().lower()


normalize = normalize_string


def normalize_artist(artist: Any) -> str:
    text = normalize_string(artist)
    if not text:
        return ""
    text = re.sub(r"\b(?:feat|featuring|ft|with)\b.*$", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_album(album: Any) -> str:
    text = normalize_string(album)
    if not text:
        return ""
    text = _ALBUM_BRACKETED_NOISE_RE.sub(" ", text)
    text = re.sub(
        r"\b(?:remaster(?:ed)?|deluxe|expanded|anniversary|edition|special edition|bonus tracks?)\b.*$",
        "",
        text,
    )
    text = re.sub(r"\(.*?\)", "", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_track_title(title: Any) -> str:
    text = _coerce_text(title)
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00A0", " ")
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_duration(duration: Any) -> str:
    text = _coerce_text(duration).strip()
    if not text:
        return ""

    text = text.replace(".", ":").replace("-", ":")
    parts = [part for part in text.split(":") if part != ""]

    if len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        return ""

    try:
        total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    except ValueError:
        return ""

    total_minutes, remaining_seconds = divmod(total_seconds, 60)
    return f"{total_minutes:02d}:{remaining_seconds:02d}"


def normalize_duration_ms(ms: int | None) -> str:
    if not ms or ms <= 0:
        return ""
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def duration_to_seconds(duration: Any) -> Optional[int]:
    if duration is None or duration == "":
        return None
    if isinstance(duration, bool):
        return None
    if isinstance(duration, (int, float)):
        seconds = int(duration)
        return seconds if seconds > 0 else None

    text = normalize_duration(duration)
    if not text:
        return None

    try:
        minutes_text, seconds_text = text.split(":")
        return int(minutes_text) * 60 + int(seconds_text)
    except ValueError:
        return None


def strip_leading_track_prefix(value: Any) -> str:
    text = normalize_track_title(_path_stem(value))
    if not text:
        return ""
    match = _LEADING_TRACK_PREFIX_RE.match(text)
    if not match:
        return text
    remainder = text[match.end() :].strip()
    return remainder or text


def strip_ytdlp_noise(value: Any) -> str:
    text = normalize_track_title(value)
    if not text:
        return ""

    previous = None
    while previous != text:
        previous = text
        text = _TRAILING_BRACKETED_NOISE_RE.sub("", text)
        text = _TRAILING_DASH_NOISE_RE.sub("", text)
        text = _PROVIDED_TO_YOUTUBE_RE.sub("", text)
        text = re.sub(r"\s*[-_|]+\s*$", "", text)
        text = _MULTI_SPACE_RE.sub(" ", text).strip()

    return text


def normalize_local_track_name(value: Any) -> str:
    text = _path_stem(value)
    if not text:
        return ""
    text = normalize_track_title(text)
    text = strip_leading_track_prefix(text)
    text = strip_ytdlp_noise(text)
    text = _SEPARATOR_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip(" ._-")


def normalize_track_filename(value: Any) -> str:
    return normalize_string(normalize_local_track_name(value))


def sanitize_filename_component(value: Any) -> str:
    text = normalize_track_title(value)
    if not text:
        return ""
    text = strip_ytdlp_noise(text)
    text = _INVALID_FILENAME_CHARS_RE.sub(" ", text)
    text = _SEPARATOR_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip(" ._-")
    return text


def track_number_width(total_tracks: int | None) -> int:
    if total_tracks and total_tracks > 0:
        return max(1, len(str(total_tracks)))
    return 2


def build_track_filename(
    track_number: int,
    title: Any,
    ext: str,
    total_tracks: int | None = None,
) -> str:
    if track_number <= 0:
        raise ValueError("track_number must be a positive integer")

    width = track_number_width(total_tracks if total_tracks is not None else track_number)
    prefix = f"{track_number:0{width}d}"
    safe_title = sanitize_filename_component(title) or "track"

    suffix = _coerce_text(ext).strip()
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix.lstrip('.')}"

    return f"{prefix}-{safe_title}{suffix}"


def extract_track_number(value: Any) -> Optional[int]:
    text = normalize_track_title(_path_stem(value))
    if not text:
        return None
    match = _LEADING_TRACK_PREFIX_RE.match(text)
    if not match:
        return None
    try:
        return int(match.group("num"))
    except (TypeError, ValueError):
        return None


def natural_sort_key(value: Any) -> list[tuple[int, Any]]:
    text = _path_stem(value)
    return [
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"(\d+)", text)
        if part
    ]
