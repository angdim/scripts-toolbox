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


def test_albumtool_source_is_conditional(repo_root: Path, python_executable: str, tmp_path: Path) -> None:
    help_result = run_command(
        [python_executable, "tools/media/audio/python/albumtool.py", "split-sfa", "--help"],
        cwd=repo_root,
    )
    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert "--split-profile" in help_result.stdout

    scan_result = run_command(
        [python_executable, "tools/media/audio/python/albumtool.py", "scan", "-d", str(tmp_path)],
        cwd=repo_root,
    )
    assert scan_result.returncode == 0, scan_result.stdout + scan_result.stderr
    assert "изисква -S/--source" in scan_result.stdout

    (tmp_path / "01 - Opening.mp3").write_bytes(b"fake")
    (tmp_path / "02 - Closing.mp3").write_bytes(b"fake")
    tag_result = run_command(
        [
            python_executable,
            "tools/media/audio/python/albumtool.py",
            "tg",
            "-d",
            str(tmp_path),
            "-a",
            "Narrator",
            "-A",
            "Audio Book",
            "-n",
        ],
        cwd=repo_root,
    )
    assert tag_result.returncode == 0, tag_result.stdout + tag_result.stderr
    assert "Локален режим" in tag_result.stdout
    assert "Тагване: 01 - Opening.mp3" in tag_result.stdout


def test_albumtool_short_command_aliases(repo_root: Path, python_executable: str) -> None:
    aliases = ["sc", "rn", "ren", "tg", "ra", "rd", "cov", "ch", "ech", "sfs"]

    for alias in aliases:
        result = run_command(
            [python_executable, "tools/media/audio/python/albumtool.py", alias, "--help"],
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
