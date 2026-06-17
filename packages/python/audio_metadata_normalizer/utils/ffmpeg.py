# audio_metadata_normalizer/utils/ffmpeg.py

"""
Общи ffmpeg операции.

Функциите в този модул не прекодират аудиото. Използва се stream copy
чрез `-c copy`, за да се запазят форматът и кодекът на входния файл.
"""

import os
import subprocess


def ffmpeg_tag_file(
    input_path: str,
    output_path: str,
    meta: dict,
    cover_path: str | None = None,
    id3v2_version: int | None = None,
):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
    ]

    if cover_path:
        cmd += ["-i", cover_path]

    cmd += [
        "-map", "0",
        "-map_metadata", "0",
        "-c", "copy",
    ]

    if cover_path:
        cmd += [
            "-map", "1",
            "-disposition:v:0", "attached_pic",
        ]

    if id3v2_version is not None and os.path.splitext(output_path)[1].lower() == ".mp3":
        cmd += [
            "-id3v2_version", str(id3v2_version),
            "-write_id3v1", "0",
        ]

    for key, value in meta.items():
        if value is None or value == "":
            continue
        cmd += ["-metadata", f"{key}={value}"]

    cmd.append(output_path)

    try:
        subprocess.run(cmd, check=True)
    except Exception:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise
