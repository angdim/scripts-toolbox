#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
Изрязва видео сегменти по говорители въз основа на transcript файл с timestamp-и.
"""

import re
import sys
import os
import subprocess

# Формат:
# Име — HH:MM:SS
header_pattern = re.compile(r"^(.+?)\s+—\s+(\d{1,2}:\d{2}:\d{2})$")

PAUSE_SECONDS = 0  # 0 = без пауза


def parse_time(t):
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


def format_time(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02}:{m:02}:{s:02}"


def get_video_duration(video_file):
    """Връща дължината на видеото в секунди чрез ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", video_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())


def load_transcript(input_file):
    entries = []
    with open(input_file, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            match = header_pattern.match(line)
            if match:
                speaker, time_str = match.groups()
                entries.append((speaker, parse_time(time_str)))
    return entries


def build_segments(entries, video_duration):
    segments = {}

    for i, (speaker, start) in enumerate(entries):
        if i < len(entries) - 1:
            end = entries[i + 1][1]
        else:
            end = video_duration  # последна реплика → до края на видеото

        if speaker not in segments:
            segments[speaker] = []

        segments[speaker].append((start, end))

    return segments


if __name__ == "__main__":
    transcript = sys.argv[1]
    video = sys.argv[2]

    video_ext = os.path.splitext(video)[1]  # .mp4, .mkv, .mov …

    entries = load_transcript(transcript)
    video_duration = get_video_duration(video)
    segments = build_segments(entries, video_duration)

    for speaker, segs in segments.items():
        safe = speaker.replace(" ", "_")
        list_file = f"{safe}_concat.txt"

        with open(list_file, "w", encoding="utf-8") as f:
            for i, (start, end) in enumerate(segs):
                duration = end - start
                out = f"{safe}_{i:03}{video_ext}"

                # изрязване на сегмента
                os.system(
                    f'ffmpeg -y -ss {format_time(start)} -t {format_time(duration)} '
                    f'-i "{video}" -c copy "{out}"'
                )
                f.write(f"file '{out}'\n")

                # пауза
                if PAUSE_SECONDS > 0:
                    pause = f"{safe}_pause_{i:03}{video_ext}"
                    os.system(
                        f'ffmpeg -y -f lavfi -i color=black:s=1920x1080:d={PAUSE_SECONDS} '
                        f'-f lavfi -i anullsrc -shortest "{pause}"'
                    )
                    f.write(f"file '{pause}'\n")

        final = f"{safe}_video{video_ext}"

        # конкатенация
        if PAUSE_SECONDS == 0:
            os.system(f'ffmpeg -y -f concat -safe 0 -i "{list_file}" -c copy "{final}"')
        else:
            os.system(
                f'ffmpeg -y -f concat -safe 0 -i "{list_file}" '
                f'-c:v libx264 -c:a aac "{final}"'
            )

        print(f"Готово: {final}")

