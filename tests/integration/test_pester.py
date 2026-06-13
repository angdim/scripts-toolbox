from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.script_runner import run_command

pytestmark = [pytest.mark.integration, pytest.mark.powershell]


def test_pester_suite_passes(repo_root: Path, tmp_path: Path) -> None:
    pester_tests = repo_root / "tests" / "powershell"
    result = run_command(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            f"Invoke-Pester -Path '{pester_tests}' -CI",
        ],
        cwd=tmp_path,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
