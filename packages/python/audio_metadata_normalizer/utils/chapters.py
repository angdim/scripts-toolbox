# audio_metadata_normalizer/utils/chapters.py

"""
Общи функции за генериране, парсване и вграждане на chapters.

Модулът не зависи от Discogs или MusicBrainz. Работи само с общата trackmap
структура:
[
    {"title": "...", "start": "00:00:00.000"},
    ...
]

Поддържани файлови формати:
- human: два реда за всяка глава - заглавие, после начален момент;
- ogm: старият CHAPTERXX/CHAPTERXXNAME формат, който FFmpeg чете директно.
"""

from __future__ import annotations

from typing import Dict, List
import os
import re
import subprocess
import tempfile


CHAPTER_FORMAT_CHOICES = ("human", "ogm")
_TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}$")
_COLON_MS_TIMESTAMP_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}):(\d{3})$")


def normalize_chapter_timestamp(value: str) -> str:
    """Нормализира timestamp до HH:MM:SS.mmm и приема HH:MM:SS:mmm като поправима грешка."""

    text = value.strip()
    colon_ms = _COLON_MS_TIMESTAMP_RE.fullmatch(text)
    if colon_ms:
        return f"{colon_ms.group(1)}.{colon_ms.group(2)}"

    if _TIMESTAMP_RE.fullmatch(text):
        return text

    raise ValueError(
        f"Невалиден timestamp: {value}. Очакван формат: HH:MM:SS.mmm "
        "(например 00:21:18.030)."
    )


def generate_human_chapter_file(chapters: List[Dict[str, str]], output_path: str):
    """Записва човешки четим chapter файл: заглавие, начален момент, празен ред."""

    lines = [
        "# albumtool chapters format: human-v1",
        "# Редактирай заглавието и началния момент под него във формат HH:MM:SS.mmm.",
        "",
    ]

    for chapter in chapters:
        lines.append(chapter["title"])
        lines.append(chapter["start"])
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as chapter_file:
        chapter_file.write("\n".join(lines).rstrip() + "\n")


def generate_ogm_chapter_file(chapters: List[Dict[str, str]], output_path: str):
    lines = []

    for i, chapter in enumerate(chapters, start=1):
        idx = f"{i:02d}"
        lines.append(f"CHAPTER{idx}={chapter['start']}")
        lines.append(f"CHAPTER{idx}NAME={chapter['title']}")

    with open(output_path, "w", encoding="utf-8") as chapter_file:
        chapter_file.write("\n".join(lines))


def generate_chapter_file(
    chapters: List[Dict[str, str]],
    output_path: str,
    chapter_format: str = "human",
):
    """Записва chapter файл в избрания формат."""

    if chapter_format == "human":
        generate_human_chapter_file(chapters, output_path)
        return

    if chapter_format == "ogm":
        generate_ogm_chapter_file(chapters, output_path)
        return

    raise ValueError(f"Неподдържан chapter формат: {chapter_format}")


def is_ogm_chapter_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as chapter_file:
        for line in chapter_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            return line.startswith("CHAPTER") and "=" in line

    return False


def parse_ogm_chapter_file(path: str) -> List[Dict[str, str]]:
    chapters: Dict[str, Dict[str, str]] = {}

    with open(path, "r", encoding="utf-8") as chapter_file:
        for line in chapter_file:
            line = line.strip()
            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            if key.startswith("CHAPTER") and key.endswith("NAME"):
                idx = key.replace("CHAPTER", "").replace("NAME", "")
                if not idx.isdigit():
                    continue
                chapters.setdefault(idx, {})["title"] = value
            elif key.startswith("CHAPTER"):
                idx = key.replace("CHAPTER", "")
                if not idx.isdigit():
                    continue
                chapters.setdefault(idx, {})["start"] = normalize_chapter_timestamp(value)

    result = []
    for idx in sorted(chapters.keys(), key=lambda item: int(item)):
        chapter = chapters[idx]
        if "title" in chapter and "start" in chapter:
            result.append(chapter)

    return result


def parse_human_chapter_file(path: str) -> List[Dict[str, str]]:
    """Чете human-v1 chapter файл: title line + start line за всяка глава."""

    meaningful_lines = []
    with open(path, "r", encoding="utf-8") as chapter_file:
        for raw_line in chapter_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            meaningful_lines.append(line)

    result = []
    for index in range(0, len(meaningful_lines), 2):
        try:
            title = meaningful_lines[index]
            start = normalize_chapter_timestamp(meaningful_lines[index + 1])
        except IndexError:
            break

        result.append({"title": title, "start": start})

    return result


def parse_chapter_file(path: str) -> List[Dict[str, str]]:
    """Автоматично разпознава human или OGM chapter файл и го парсва."""

    if is_ogm_chapter_file(path):
        return parse_ogm_chapter_file(path)

    return parse_human_chapter_file(path)


def build_ffmpeg_chapter_input_file(chapter_file: str) -> tuple[str, bool]:
    """Връща OGM/FFmpeg-съвместим chapter файл и дали е временен."""

    if is_ogm_chapter_file(chapter_file):
        return chapter_file, False

    chapters = parse_human_chapter_file(chapter_file)
    temp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".chapters.ogm.txt",
        delete=False,
    )
    temp.close()
    generate_ogm_chapter_file(chapters, temp.name)
    return temp.name, True


def embed_chapters_ffmpeg(input_file: str, output_file: str, chapter_file: str):
    ffmpeg_chapter_file, is_temp = build_ffmpeg_chapter_input_file(chapter_file)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-i", ffmpeg_chapter_file,
        "-map_metadata", "1",
        "-map", "0",
        "-c", "copy",
        output_file
    ]

    try:
        subprocess.run(cmd, check=True)
    except Exception:
        if os.path.exists(output_file):
            os.remove(output_file)
        raise
    finally:
        if is_temp and os.path.exists(ffmpeg_chapter_file):
            os.remove(ffmpeg_chapter_file)
