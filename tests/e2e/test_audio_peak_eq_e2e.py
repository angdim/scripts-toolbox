from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.media_factory import make_test_mp4
from tests.helpers.script_runner import run_command

pytestmark = [pytest.mark.e2e, pytest.mark.slow, pytest.mark.media, pytest.mark.linux]


def test_audio_peak_eq_processes_video_audio_and_keeps_video_stream(repo_root: Path, tmp_path: Path) -> None:
    input_mp4 = make_test_mp4(tmp_path / "input.mp4", duration=1.0)
    output_mp4 = tmp_path / "output.mp4"
    script = repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py"

    run_command(
        [
            script,
            "-i",
            input_mp4,
            "-o",
            output_mp4,
            "-B",
            "--balance-mode",
            "all",
            "-p",
            "speech_cleanup",
            "-t",
            "-6",
            "--overwrite",
        ],
        cwd=repo_root,
        timeout=180,
        check=True,
    )

    assert output_mp4.exists()
    probe = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            output_mp4,
        ],
        check=True,
    )
    streams = probe.stdout.strip().splitlines()
    assert "video" in streams
    assert "audio" in streams
