from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.script_runner import run_command

pytestmark = [pytest.mark.integration, pytest.mark.linux]


def test_normalize_file_names_dry_run_does_not_rename(repo_root: Path, tmp_path: Path) -> None:
    target = tmp_path / "files"
    target.mkdir()
    original = target / "Песен ? 01.txt"
    original.write_text("data", encoding="utf-8")

    script = repo_root / "tools" / "files" / "names" / "bash" / "normalize_file_names.sh"
    result = run_command(["bash", script, "--dry-run", target], cwd=repo_root, check=True)

    assert original.exists()
    assert "Променени: 1" in result.stdout


def test_normalize_file_names_renames_files_only(repo_root: Path, tmp_path: Path) -> None:
    target = tmp_path / "files"
    target.mkdir()
    original = target / "Песен ? 01.txt"
    original.write_text("data", encoding="utf-8")
    directory = target / "Дир ?"
    directory.mkdir()

    script = repo_root / "tools" / "files" / "names" / "bash" / "normalize_file_names.sh"
    run_command(["bash", script, target], cwd=repo_root, check=True)

    assert not original.exists()
    assert (target / "Песен_01.txt").exists()
    assert directory.exists(), "file-only скриптът не трябва да преименува директории"


def test_normalize_dir_names_renames_directories_only(repo_root: Path, tmp_path: Path) -> None:
    target = tmp_path / "root"
    nested = target / "Дир ?" / "Sub Dir !"
    nested.mkdir(parents=True)
    file_with_bad_name = nested / "file ?.txt"
    file_with_bad_name.write_text("data", encoding="utf-8")

    script = repo_root / "tools" / "files" / "names" / "bash" / "normalize_dir_names.sh"
    run_command(["bash", script, target], cwd=repo_root, check=True)

    renamed_parent = target / "Дир_"
    renamed_nested = renamed_parent / "Sub_Dir_"
    assert renamed_nested.is_dir()
    assert (renamed_nested / "file ?.txt").exists(), "dir-only скриптът не трябва да преименува файлове"


def test_normalize_all_names_updates_directories_and_files(repo_root: Path, tmp_path: Path) -> None:
    target = tmp_path / "root"
    nested = target / "Дир ?"
    nested.mkdir(parents=True)
    (nested / "Файл ?.txt").write_text("data", encoding="utf-8")

    script = repo_root / "tools" / "files" / "names" / "bash" / "normalize_all_names.sh"
    run_command(["bash", script, target], cwd=repo_root, check=True)

    assert (target / "Дир_" / "Файл_.txt").exists()
