from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.media_factory import make_imbalanced_stereo_wav, make_sine_wav
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
    assert "Ред на обработка: channel balance -> EQ -> peak нормализация." in result.stdout
