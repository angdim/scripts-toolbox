# audio_metadata_normalizer/utils/chapters.py

"""
Общи функции за генериране, парсване и вграждане на OGM/FFmpeg chapters.

Модулът не зависи от Discogs или MusicBrainz. Работи само с общата trackmap
структура:
[
    {"title": "...", "start": "00:00:00.000"},
    ...
]
"""

from typing import Dict, List
import os
import subprocess


def generate_ogm_chapter_file(chapters: List[Dict[str, str]], output_path: str):
    lines = []

    for i, chapter in enumerate(chapters, start=1):
        idx = f"{i:02d}"
        lines.append(f"CHAPTER{idx}={chapter['start']}")
        lines.append(f"CHAPTER{idx}NAME={chapter['title']}")

    with open(output_path, "w", encoding="utf-8") as chapter_file:
        chapter_file.write("\n".join(lines))


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
                chapters.setdefault(idx, {})["start"] = value

    result = []
    for idx in sorted(chapters.keys(), key=lambda item: int(item)):
        chapter = chapters[idx]
        if "title" in chapter and "start" in chapter:
            result.append(chapter)

    return result


def embed_chapters_ffmpeg(input_file: str, output_file: str, chapter_file: str):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-i", chapter_file,
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
