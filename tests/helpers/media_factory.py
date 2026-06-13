from __future__ import annotations

from pathlib import Path

from tests.helpers.script_runner import run_command


def make_sine_wav(path: Path, *, duration: float = 0.5, frequency: int = 1000) -> Path:
    """Create a small deterministic WAV fixture with FFmpeg."""
    run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration={duration}",
            str(path),
        ],
        check=True,
    )
    return path


def make_imbalanced_stereo_wav(path: Path, *, duration: float = 0.5) -> Path:
    """Create a stereo WAV where the right channel is quieter than the left channel."""
    run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-filter_complex",
            "[1:a]volume=-6dB[right];[0:a][right]amerge=inputs=2",
            "-ac",
            "2",
            str(path),
        ],
        check=True,
    )
    return path


def make_test_mp4(path: Path, *, duration: float = 0.5) -> Path:
    """Create a tiny MP4 fixture with one video stream and one audio stream."""
    run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=160x120:rate=25:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration}",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        timeout=90,
    )
    return path
