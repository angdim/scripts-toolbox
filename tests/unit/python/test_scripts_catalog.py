from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.importing import import_module_from_path
from tests.helpers.script_runner import run_command


def catalog_module(repo_root: Path):
    return import_module_from_path(
        repo_root / "tools" / "catalog" / "python" / "scripts_catalog.py",
        "scripts_catalog_tool",
    )


def test_catalog_builds_active_entries(repo_root: Path) -> None:
    module = catalog_module(repo_root)
    catalog = module.build_catalog(repo_root)
    commands = {entry.command for entry in catalog.active}

    assert "audio_peak_eq" in commands
    assert "scripts-catalog" in commands
    assert all(entry.entrypoint and not entry.no_path for entry in catalog.active)


def test_catalog_search_and_find(repo_root: Path) -> None:
    module = catalog_module(repo_root)
    catalog = module.build_catalog(repo_root)

    results = module.search_entries(catalog.active, "channel balance")
    assert any(entry.command == "audio_peak_eq" for entry in results)
    assert module.find_entry(catalog.active, "audio_peak_eq").path.endswith("audio_peak_eq.py")


def test_catalog_removed_yaml_parser(repo_root: Path, tmp_path: Path) -> None:
    module = catalog_module(repo_root)
    removed_file = tmp_path / "removed.yaml"
    removed_file.write_text(
        "removed:\n"
        "  - command: old_tool\n"
        "    path: tools/old/old_tool.py\n"
        "    removed_at: 2026-06-13\n"
        "    replacement: new_tool\n"
        "    reason: replaced\n"
        "    purpose: did old work\n",
        encoding="utf-8",
    )

    removed = module.parse_removed_yaml(removed_file)

    assert len(removed) == 1
    assert removed[0].command == "old_tool"
    assert removed[0].replacement == "new_tool"


def test_catalog_generate_and_validate(repo_root: Path, tmp_path: Path) -> None:
    script = repo_root / "tools" / "catalog" / "python" / "scripts_catalog.py"
    markdown = tmp_path / "catalog.md"
    json_file = tmp_path / "catalog.json"

    generate = run_command(
        [script, "generate", "--markdown", markdown, "--json", json_file],
        cwd=repo_root,
        check=True,
    )
    assert "Генериран Markdown" in generate.stdout

    validate = run_command(
        [script, "validate", "--markdown", markdown, "--json", json_file],
        cwd=repo_root,
        check=True,
    )
    assert "Каталогът е актуален" in validate.stdout

    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert any(entry["command"] == "audio_peak_eq" for entry in data["active"])


def test_catalog_cli_show_and_help(repo_root: Path) -> None:
    script = repo_root / "tools" / "catalog" / "python" / "scripts_catalog.py"

    show = run_command([script, "show", "audio_peak_eq"], cwd=repo_root, check=True)
    assert "Команда:      audio_peak_eq" in show.stdout

    help_result = run_command([script, "help", "audio_peak_eq"], cwd=repo_root, check=True)
    assert "audio_peak_eq --help" in help_result.stdout
