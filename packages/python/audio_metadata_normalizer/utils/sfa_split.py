# audio_metadata_normalizer/utils/sfa_split.py

"""
Разделяне на single-file албум на отделни тракове чрез chapter файл.

Логиката е насочена към безопасни lossy профили за автомобилни infotainment
системи: MP3 чрез libmp3lame или M4A чрез FFmpeg AAC. Битрейтът по подразбиране
се избира автоматично като най-близкия стандартен bitrate, който е по-голям или
равен на текущия bitrate на входния аудио поток.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_metadata_normalizer.utils.chapters import normalize_chapter_timestamp
from audio_metadata_normalizer.utils.cover_profile import (
    ffmpeg_id3v2_version_for_profile,
    prepared_cover_path,
)
from audio_metadata_normalizer.utils.normalize import build_track_filename

STANDARD_BITRATES_KBPS = (96, 112, 128, 144, 160, 192, 224, 256, 320)
LOSSLESS_CODECS = {"flac", "pcm_s16le", "pcm_s24le", "pcm_s32le", "alac", "wavpack"}


@dataclass(frozen=True)
class SplitProfile:
    """Описание на безопасен output encoding профил."""

    name: str
    extension: str
    codec: str
    max_bitrate_kbps: int
    cover_profile: str


@dataclass(frozen=True)
class AudioInfo:
    """Минимална информация за входния аудио поток."""

    codec_name: str | None
    bit_rate_bps: int | None
    sample_rate_hz: int | None
    duration_seconds: float | None


@dataclass(frozen=True)
class SplitSegment:
    """Един изходен трак, изчислен от началото на текущата и следващата глава."""

    index: int
    title: str
    start: str
    end: str | None
    output_path: str


SPLIT_PROFILES = {
    "lexus-mp3": SplitProfile(
        name="lexus-mp3",
        extension=".mp3",
        codec="libmp3lame",
        max_bitrate_kbps=320,
        cover_profile="lexus-jpeg-500",
    ),
    "lexus-m4a": SplitProfile(
        name="lexus-m4a",
        extension=".m4a",
        codec="aac",
        max_bitrate_kbps=320,
        cover_profile="lexus-jpeg-500",
    ),
}


def parse_bitrate_kbps(value: str) -> int:
    """Парсва стойност като `128k` или `128` до kbps."""

    text = value.strip().lower()
    if text.endswith("k"):
        text = text[:-1]
    try:
        bitrate = int(text)
    except ValueError as exc:
        raise ValueError(f"Невалиден bitrate: {value}") from exc

    if bitrate <= 0:
        raise ValueError("Bitrate трябва да е положително число.")

    return bitrate


def format_bitrate(kbps: int) -> str:
    return f"{kbps}k"


def choose_standard_bitrate_kbps(
    source_bitrate_bps: int | None,
    codec_name: str | None,
    max_bitrate_kbps: int = 320,
    fallback_lossy_kbps: int = 128,
) -> tuple[int, str | None]:
    """Избира стандартен bitrate >= входния, когато това е приложимо."""

    if not source_bitrate_bps or source_bitrate_bps <= 0:
        return fallback_lossy_kbps, "Липсва входен bitrate; използва се fallback 128k."

    source_kbps = max(1, int((source_bitrate_bps + 999) // 1000))
    if codec_name in LOSSLESS_CODECS:
        return max_bitrate_kbps, (
            "Входният поток е lossless/PCM; използва се максималният безопасен "
            f"bitrate {max_bitrate_kbps}k за избрания lossy профил."
        )

    for bitrate in STANDARD_BITRATES_KBPS:
        if bitrate >= source_kbps and bitrate <= max_bitrate_kbps:
            return bitrate, None

    return max_bitrate_kbps, (
        f"Входният bitrate е около {source_kbps}k и е над безопасната скала; "
        f"използва се максимумът {max_bitrate_kbps}k."
    )


def ffprobe_audio_info(audio_file: str) -> AudioInfo:
    """Чете codec, bitrate, sample rate и duration чрез ffprobe."""

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,bit_rate,sample_rate:format=duration,bit_rate",
            "-of",
            "json",
            audio_file,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    data = json.loads(result.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}

    bit_rate = _optional_int(stream.get("bit_rate")) or _optional_int(fmt.get("bit_rate"))
    return AudioInfo(
        codec_name=stream.get("codec_name"),
        bit_rate_bps=bit_rate,
        sample_rate_hz=_optional_int(stream.get("sample_rate")),
        duration_seconds=_optional_float(fmt.get("duration")),
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def timestamp_to_seconds(timestamp: str) -> float:
    """Конвертира HH:MM:SS.mmm до секунди."""

    timestamp = normalize_chapter_timestamp(timestamp)
    parts = timestamp.split(":")
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def seconds_to_timestamp(seconds: float) -> str:
    """Конвертира секунди до HH:MM:SS.mmm."""

    if seconds < 0:
        raise ValueError("Timestamp не може да бъде отрицателен.")

    whole_ms = int(round(seconds * 1000))
    ms = whole_ms % 1000
    total_seconds = whole_ms // 1000
    sec = total_seconds % 60
    total_minutes = total_seconds // 60
    minute = total_minutes % 60
    hour = total_minutes // 60
    return f"{hour:02d}:{minute:02d}:{sec:02d}.{ms:03d}"


def format_filter_seconds(timestamp: str) -> str:
    """Връща timestamp като секунди с millisecond точност за FFmpeg filters."""

    return f"{timestamp_to_seconds(timestamp):.3f}"


def build_split_segments(
    chapters: list[dict[str, str]],
    output_dir: str,
    extension: str,
    duration_seconds: float | None = None,
) -> list[SplitSegment]:
    """Изчислява сегментите и имената на изходните файлове."""

    total = len(chapters)
    segments: list[SplitSegment] = []
    for index, chapter in enumerate(chapters, start=1):
        next_chapter = chapters[index] if index < total else None
        end = next_chapter["start"] if next_chapter else None
        if end is None and duration_seconds:
            end = seconds_to_timestamp(duration_seconds)

        filename = build_track_filename(index, chapter["title"], extension, total)
        segments.append(
            SplitSegment(
                index=index,
                title=chapter["title"],
                start=chapter["start"],
                end=end,
                output_path=os.path.join(output_dir, filename),
            )
        )

    return segments


def build_split_command(
    input_file: str,
    segment: SplitSegment,
    profile: SplitProfile,
    bitrate_kbps: int,
    sample_rate_hz: int | None,
    metadata: dict[str, str | None],
    cover_path: str | None = None,
) -> list[str]:
    """Създава FFmpeg команда за един изходен трак."""

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        input_file,
    ]

    if cover_path:
        command += ["-i", cover_path]

    command += ["-map", "0:a:0"]
    if cover_path:
        command += ["-map", "1:v:0", "-disposition:v:0", "attached_pic"]

    atrim = f"atrim=start={format_filter_seconds(segment.start)}"
    if segment.end:
        atrim += f":end={format_filter_seconds(segment.end)}"
    command += ["-af", f"{atrim},asetpts=PTS-STARTPTS"]

    if not cover_path:
        command += ["-vn"]

    command += ["-c:a", profile.codec, "-b:a", format_bitrate(bitrate_kbps)]
    if cover_path:
        command += ["-c:v", "copy"]
    if sample_rate_hz:
        command += ["-ar", str(sample_rate_hz)]

    id3_version = ffmpeg_id3v2_version_for_profile(segment.output_path, profile.cover_profile)
    if id3_version is not None:
        command += ["-id3v2_version", str(id3_version), "-write_id3v1", "0"]

    for key, value in metadata.items():
        if value:
            command += ["-metadata", f"{key}={value}"]

    command.append(segment.output_path)
    return command


def split_sfa_file(
    input_file: str,
    chapters: list[dict[str, str]],
    output_dir: str,
    profile_name: str,
    artist: str | None,
    album: str | None,
    cover_path: str | None,
    bitrate: str = "auto",
    sample_rate_hz: int | None = 48000,
    dry_run: bool = False,
    force: bool = False,
) -> list[SplitSegment]:
    """Разделя SFA файл според chapter файл и кодира всеки трак."""

    profile = SPLIT_PROFILES[profile_name]
    info = ffprobe_audio_info(input_file)
    if bitrate == "auto":
        bitrate_kbps, warning = choose_standard_bitrate_kbps(
            info.bit_rate_bps,
            info.codec_name,
            profile.max_bitrate_kbps,
        )
        if warning:
            print(f"Предупреждение: {warning}")
    else:
        bitrate_kbps = parse_bitrate_kbps(bitrate)

    segments = build_split_segments(chapters, output_dir, profile.extension, info.duration_seconds)
    conflicts = [segment.output_path for segment in segments if os.path.exists(segment.output_path)]
    if conflicts and not force:
        raise FileExistsError(
            "Целеви файлове вече съществуват. Използвай --force за презапис: "
            + ", ".join(os.path.basename(path) for path in conflicts[:5])
        )

    print(f"Профил: {profile.name}")
    print(f"Bitrate: {format_bitrate(bitrate_kbps)}")
    if sample_rate_hz:
        print(f"Sample rate: {sample_rate_hz} Hz")
    print(f"Изходна директория: {output_dir}")

    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)

    with prepared_cover_path(cover_path, profile.cover_profile, dry_run=dry_run) as effective_cover:
        for segment in segments:
            metadata = {
                "title": segment.title,
                "artist": artist,
                "album": album,
                "album_artist": artist,
                "track": f"{segment.index}/{len(segments)}",
            }
            command = build_split_command(
                input_file,
                segment,
                profile,
                bitrate_kbps,
                sample_rate_hz,
                metadata,
                effective_cover,
            )
            print(f"{segment.index:02d}. {segment.start} -> {segment.end or 'край'} | {segment.title}")
            if dry_run:
                print("+ " + " ".join(command))
                continue

            subprocess.run(command, check=True)

    if not dry_run:
        write_playlist(output_dir, segments)
    return segments


def write_playlist(output_dir: str, segments: list[SplitSegment]) -> None:
    """Създава M3U8 playlist в правилния ред."""

    playlist_path = Path(output_dir) / "playlist.m3u8"
    lines = ["#EXTM3U"]
    lines.extend(os.path.basename(segment.output_path) for segment in segments)
    playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
