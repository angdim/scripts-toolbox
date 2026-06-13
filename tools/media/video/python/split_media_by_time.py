#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
Разделя audio/video файл на последователни части с фиксирана продължителност и малко припокриване.
"""

import subprocess
import sys
import os

CHUNK_DURATION = 29 * 60   # 20 минути
OVERLAP = 5               # 10 секунди
PREFIX = "part_"

def get_media_duration(filename):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", filename
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return float(result.stdout.strip())

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"

def split_media(input_file):
    base, ext = os.path.splitext(input_file)
    ext = ext.lstrip(".")

    total_duration = get_media_duration(input_file)
    print(f"Total duration: {format_time(total_duration)}")

    start = 0
    part = 1

    while start < total_duration:
        end = start + CHUNK_DURATION
        if end > total_duration:
            end = total_duration

        output_file = f"{PREFIX}{part:02}.{ext}"

        print(f"Creating part {part}: {format_time(start)} - {format_time(end)}")

        subprocess.run([
            "ffmpeg",
            "-y",
            "-ss", str(start),
            "-to", str(end),
            "-i", input_file,
            "-c", "copy",
            output_file
        ])

        if end >= total_duration:
            # последна част – прекъсваме
            break

        part += 1
        start = end - OVERLAP

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "input.mp4"

    if not os.path.isfile(input_file):
        print(f"Грешка: Файлът '{input_file}' не съществува.")
        sys.exit(1)

    split_media(input_file)

