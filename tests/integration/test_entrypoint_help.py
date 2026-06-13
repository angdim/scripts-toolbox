from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.script_runner import run_command

pytestmark = pytest.mark.integration


HELP_CASES = [
    (["bash", "bootstrap/linux/install-to-path.sh", "--help"], "Употреба"),
    (["tools/media/audio/python/audio_peak_eq.py", "--help"], "peak"),
    (["tools/text/transcript/python/split_by_speaker.py", "--help"], "говорители"),
    (["bash", "tools/media/audio/bash/generate_playlist.sh", "--help"], "Употреба"),
    (["bash", "tools/files/names/bash/normalize_file_names.sh", "--help"], "Употреба"),
    (["bash", "tools/files/names/bash/normalize_dir_names.sh", "--help"], "Употреба"),
    (["bash", "tools/files/names/bash/normalize_all_names.sh", "--help"], "Употреба"),
]


@pytest.mark.parametrize(("command", "expected"), HELP_CASES)
def test_entrypoint_help_smoke(repo_root: Path, command: list[str], expected: str) -> None:
    result = run_command(command, cwd=repo_root)
    assert result.returncode == 0, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert expected.lower() in combined.lower()


def test_albumtool_help_uses_project_venv(repo_root: Path, python_executable: str) -> None:
    result = run_command(
        [python_executable, "tools/media/audio/python/albumtool.py", "--help"],
        cwd=repo_root,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "usage" in result.stdout.lower()


def test_windows_bootstrap_help(repo_root: Path) -> None:
    result = run_command(
        ["pwsh", "-NoProfile", "-File", "bootstrap/windows/Install-ToPath.ps1", "-Help"],
        cwd=repo_root,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Инсталира" in result.stdout
