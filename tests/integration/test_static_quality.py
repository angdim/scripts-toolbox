from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.script_runner import run_command

pytestmark = pytest.mark.integration


def _files(repo_root: Path, suffix: str) -> list[str]:
    return [
        str(path)
        for root in ("tools", "bootstrap", "packages")
        for path in (repo_root / root).rglob(f"*{suffix}")
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    ]


def test_python_sources_compile(repo_root: Path, python_executable: str) -> None:
    py_files = _files(repo_root, ".py")
    result = run_command([python_executable, "-m", "py_compile", *py_files], cwd=repo_root)
    assert result.returncode == 0, result.stderr


def test_ruff_and_mypy_are_clean(repo_root: Path, python_executable: str) -> None:
    py_files = _files(repo_root, ".py")

    ruff_result = run_command(
        [
            python_executable,
            "-m",
            "ruff",
            "check",
            "tools",
            "packages",
            "--exclude",
            "*/.venv/*",
            "--exclude",
            "__pycache__",
        ],
        cwd=repo_root,
    )
    assert ruff_result.returncode == 0, ruff_result.stdout + ruff_result.stderr

    mypy_result = run_command([python_executable, "-m", "mypy", *py_files], cwd=repo_root)
    assert mypy_result.returncode == 0, mypy_result.stdout + mypy_result.stderr


def test_shell_scripts_pass_shellcheck_and_bash_syntax(repo_root: Path) -> None:
    shell_files = _files(repo_root, ".sh")
    shellcheck = run_command(["shellcheck", *shell_files], cwd=repo_root)
    assert shellcheck.returncode == 0, shellcheck.stdout + shellcheck.stderr

    for shell_file in shell_files:
        syntax = run_command(["bash", "-n", shell_file], cwd=repo_root)
        assert syntax.returncode == 0, f"{shell_file}\n{syntax.stderr}"


def test_powershell_scripts_parse(repo_root: Path) -> None:
    ps_files = _files(repo_root, ".ps1")
    for ps_file in ps_files:
        result = run_command(
            [
                "pwsh",
                "-NoProfile",
                "-Command",
                f"[scriptblock]::Create((Get-Content -Raw '{ps_file}')) | Out-Null",
            ],
            cwd=repo_root,
        )
        assert result.returncode == 0, f"{ps_file}\n{result.stderr}"
