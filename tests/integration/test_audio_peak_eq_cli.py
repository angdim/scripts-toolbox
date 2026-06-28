from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.media_factory import (
    make_imbalanced_stereo_wav,
    make_sine_silence_sine_wav,
    make_sine_wav,
    make_test_mp4_with_audio_silence,
)
from tests.helpers.script_runner import run_command

pytestmark = [pytest.mark.integration, pytest.mark.media, pytest.mark.linux]


def test_audio_peak_eq_lists_presets(repo_root: Path) -> None:
    script = repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py"
    result = run_command([script, "--list-presets"], cwd=repo_root, check=True)
    assert "bass_boost" in result.stdout
    assert "mains_hum_50hz" in result.stdout


def test_audio_peak_eq_normalizes_generated_wav(repo_root: Path, tmp_path: Path) -> None:
    input_wav = make_sine_wav(tmp_path / "input.wav", duration=0.4)
    output_wav = tmp_path / "output.wav"
    script = repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py"

    result = run_command(
        [script, "-i", input_wav, "-o", output_wav, "-t", "-6", "--overwrite"],
        cwd=repo_root,
        timeout=120,
        check=True,
    )

    assert output_wav.exists()
    assert output_wav.stat().st_size > 0
    assert "Необходим gain" in result.stdout


def test_audio_peak_eq_balances_channels_before_normalization(repo_root: Path, tmp_path: Path) -> None:
    input_wav = make_imbalanced_stereo_wav(tmp_path / "imbalanced.wav", duration=0.4)
    output_wav = tmp_path / "balanced.wav"
    script = repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py"

    result = run_command(
        [script, "-i", input_wav, "-o", output_wav, "-B", "-t", "-6", "--overwrite"],
        cwd=repo_root,
        timeout=180,
        check=True,
    )

    assert output_wav.exists()
    assert output_wav.stat().st_size > 0
    assert "Channel peak нива" in result.stdout
    assert "Ред на обработка: channel balance -> филтри/EQ -> silence trim -> финална нормализация." in result.stdout


def media_duration(path: Path) -> float:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        check=True,
    )
    return float(result.stdout.strip())


def test_audio_peak_eq_trims_long_silence(repo_root: Path, tmp_path: Path) -> None:
    input_wav = make_sine_silence_sine_wav(tmp_path / "with_silence.wav")
    output_wav = tmp_path / "trimmed.wav"
    script = repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py"

    result = run_command(
        [
            script,
            "-i",
            input_wav,
            "-o",
            output_wav,
            "--trim-silence",
            "--silence-threshold",
            "-50",
            "--silence-duration",
            "0.4",
            "--keep-silence",
            "0.1",
            "-t",
            "-6",
            "--overwrite",
        ],
        cwd=repo_root,
        timeout=180,
        check=True,
    )

    assert output_wav.exists()
    assert media_duration(output_wav) < media_duration(input_wav) - 0.4
    assert "silenceremove=" in result.stdout


def test_audio_peak_eq_analyzes_silence_without_output(repo_root: Path, tmp_path: Path) -> None:
    input_wav = make_sine_silence_sine_wav(tmp_path / "with_silence.wav")
    script = repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py"

    result = run_command(
        [
            script,
            "-i",
            input_wav,
            "--analyze-silence",
            "--silence-threshold",
            "-50",
            "--silence-duration",
            "0.4",
        ],
        cwd=repo_root,
        timeout=120,
        check=True,
    )

    assert "Анализ на тишина/паузи" in result.stdout
    assert "Сегменти:" in result.stdout


def test_audio_peak_eq_trims_video_with_matching_fades(repo_root: Path, tmp_path: Path) -> None:
    input_mp4 = make_test_mp4_with_audio_silence(tmp_path / "with_silence.mp4")
    output_mp4 = tmp_path / "trimmed.mp4"
    script = repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py"

    result = run_command(
        [
            script,
            "-i",
            input_mp4,
            "-o",
            output_mp4,
            "--trim-silence",
            "--cut-transition",
            "fade",
            "--video-cut-transition",
            "fade",
            "--silence-threshold",
            "-50",
            "--silence-duration",
            "0.4",
            "--keep-silence",
            "0.1",
            "-t",
            "-6",
            "--overwrite",
        ],
        cwd=repo_root,
        timeout=240,
        check=True,
    )

    assert output_mp4.exists()
    assert media_duration(output_mp4) < media_duration(input_mp4) - 0.3
    assert "Concat silence trim" in result.stdout
    assert "fade=t=out" in result.stdout
