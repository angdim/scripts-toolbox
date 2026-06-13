import subprocess
import os
from typing import Dict, Optional


# ---------------------------------------------------------
# Helper: run ffmpeg safely
# ---------------------------------------------------------

def run_ffmpeg(cmd: list):
    """
    Run ffmpeg command and raise exception on error.
    """
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8"))


# ---------------------------------------------------------
# Build ffmpeg metadata arguments
# ---------------------------------------------------------

def build_metadata_args(metadata: Dict[str, str]) -> list:
    """
    Convert metadata dict into ffmpeg -metadata arguments.
    """
    args = []
    for key, value in metadata.items():
        args += ["-metadata", f"{key}={value}"]
    return args


# ---------------------------------------------------------
# Tag a single audio file
# ---------------------------------------------------------

def tag_file(
    input_file: str,
    output_file: str,
    metadata: Dict[str, str],
    cover_art: Optional[str] = None
):
    """
    Tag an audio file using ffmpeg.
    - input_file: original audio
    - output_file: tagged audio
    - metadata: dict with keys like:
        artist, album, title, track, date, genre
    - cover_art: path to cover image (optional)
    """

    cmd = ["ffmpeg", "-y", "-i", input_file]

    # Add cover art if available
    if cover_art and os.path.exists(cover_art):
        cmd += ["-i", cover_art, "-map", "0:a", "-map", "1:v", "-c:v", "copy"]
        cmd += ["-metadata:s:v", "title=Cover", "-metadata:s:v", "comment=Cover (front)"]
    else:
        cmd += ["-map", "0:a"]

    # Add metadata
    cmd += build_metadata_args(metadata)

    # Copy audio without re-encoding
    cmd += ["-c:a", "copy", output_file]

    run_ffmpeg(cmd)
