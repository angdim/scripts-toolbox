from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.script_runner import run_command

pytestmark = [pytest.mark.integration, pytest.mark.linux]


def test_linux_bootstrap_installs_only_marked_entrypoints(repo_root: Path, tmp_path: Path) -> None:
    source = tmp_path / "scripts-toolbox-fixture"
    tool_dir = source / "tools" / "demo" / "python"
    package_dir = source / "packages" / "python"
    target = tmp_path / "bin"
    tool_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)

    hello = tool_dir / "hello_tool.py"
    hello.write_text(
        "#!/usr/bin/env python3\n"
        "# scripts-toolbox: entrypoint\n"
        "# scripts-toolbox: command=hello-tool\n"
        "print('hello from wrapper')\n",
        encoding="utf-8",
    )
    hello.chmod(0o755)

    ignored = tool_dir / "helper.py"
    ignored.write_text(
        "#!/usr/bin/env python3\n"
        "# scripts-toolbox: no-path\n"
        "print('should not be installed')\n",
        encoding="utf-8",
    )
    ignored.chmod(0o755)

    installer = repo_root / "bootstrap" / "linux" / "install-to-path.sh"
    result = run_command(
        ["bash", installer, "--python", "--target", target, source],
        cwd=repo_root,
        check=True,
    )
    assert "hello-tool" in result.stdout

    installed = target / "hello-tool"
    assert installed.exists()
    assert not (target / "helper").exists()

    wrapper_run = run_command([installed], check=True)
    assert wrapper_run.stdout.strip() == "hello from wrapper"


def test_linux_bootstrap_dry_run_does_not_create_target(repo_root: Path, tmp_path: Path) -> None:
    source = tmp_path / "repo"
    tool_dir = source / "tools" / "demo" / "bash"
    target = tmp_path / "dry-bin"
    tool_dir.mkdir(parents=True)
    (source / "packages").mkdir()

    script = tool_dir / "demo.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "# scripts-toolbox: entrypoint\n"
        "echo demo\n",
        encoding="utf-8",
    )
    script.chmod(0o755)

    installer = repo_root / "bootstrap" / "linux" / "install-to-path.sh"
    result = run_command(
        ["bash", installer, "--bash", "--dry-run", "--target", target, source],
        cwd=repo_root,
        check=True,
    )
    assert "demo" in result.stdout
    assert not target.exists()
