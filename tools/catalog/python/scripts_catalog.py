#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# scripts-toolbox: command=scripts-catalog
"""
Енциклопедичен каталог за scripts-toolbox.

Сканира repo-то за скриптове, извлича marker-и, описания, тематична структура,
команди за помощ и генерира Markdown/JSON каталог. Поддържа и архивна секция за
изтрити скриптове чрез docs/catalog/removed-scripts.yaml.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

ENTRYPOINT_MARKER = "scripts-toolbox: entrypoint"
NO_PATH_MARKER = "scripts-toolbox: no-path"
COMMAND_RE = re.compile(r"^\s*(?:#|REM)\s*scripts-toolbox:\s*command=([A-Za-z0-9._-]+)\s*$", re.I)
PURPOSE_RE = re.compile(r"^\s*(?:#|REM)\s*Предназначение:\s*(.+?)\s*$", re.I)
SUPPORTED_SUFFIXES = {".py", ".sh", ".ps1", ".bat", ".cmd"}
IGNORED_PARTS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
}
DEFAULT_MARKDOWN = Path("docs/catalog/scripts-catalog.md")
DEFAULT_JSON = Path("docs/catalog/scripts-catalog.json")
DEFAULT_REMOVED = Path("docs/catalog/removed-scripts.yaml")


@dataclass(frozen=True)
class ScriptEntry:
    command: str
    path: str
    category: str
    topic: str
    technology: str
    platform: str
    status: str
    entrypoint: bool
    no_path: bool
    description: str
    help_command: str
    markers: list[str]


@dataclass(frozen=True)
class RemovedEntry:
    command: str
    path: str
    removed_at: str
    replacement: str
    reason: str
    purpose: str


@dataclass(frozen=True)
class Catalog:
    repo_root: str
    active: list[ScriptEntry]
    removed: list[RemovedEntry]


def find_repo_root(start: Path) -> Path:
    """Намира root директорията на scripts-toolbox repo-то."""
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in [current, *current.parents]:
        if (directory / "tools").is_dir() and (directory / "docs").is_dir():
            return directory
    raise SystemExit("Неуспешно откриване на repo root. Стартирай от scripts-toolbox директория.")


def is_ignored(path: Path, repo_root: Path) -> bool:
    """Пропуска cache/venv/generated директории при сканиране."""
    try:
        rel_parts = path.relative_to(repo_root).parts
    except ValueError:
        return True
    return any(part in IGNORED_PARTS for part in rel_parts)


def iter_script_files(repo_root: Path, include_bootstrap: bool = True) -> Iterable[Path]:
    """Връща всички потенциални скриптове от tools и, по избор, bootstrap."""
    roots = [repo_root / "tools"]
    if include_bootstrap:
        roots.append(repo_root / "bootstrap")
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES and not is_ignored(path, repo_root):
                yield path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def header_lines(path: Path, limit: int = 40) -> list[str]:
    try:
        return read_text(path).splitlines()[:limit]
    except OSError:
        return []


def detect_technology(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "Python"
    if suffix == ".sh":
        return "Bash"
    if suffix == ".ps1":
        return "PowerShell"
    if suffix in {".bat", ".cmd"}:
        return "Batch/CMD"
    return "Unknown"


def detect_platform(path: Path, technology: str) -> str:
    parts = {part.lower() for part in path.parts}
    if "windows" in parts:
        return "Windows"
    if technology in {"Bash"}:
        return "Linux/Unix"
    if technology == "PowerShell":
        return "Cross-platform PowerShell"
    if technology == "Batch/CMD":
        return "Windows"
    return "Cross-platform/Python"


def command_name_for_file(path: Path) -> str:
    for line in header_lines(path):
        match = COMMAND_RE.match(line)
        if match:
            return match.group(1)
    return path.stem


def marker_list(path: Path) -> list[str]:
    markers = []
    for line in header_lines(path):
        if "scripts-toolbox:" in line:
            markers.append(line.strip().lstrip("#").lstrip("REM").strip())
        if re.match(r"^\s*#\s*no-venv\s*$", line, re.I):
            markers.append("no-venv")
    return markers


def has_marker(path: Path, marker: str) -> bool:
    return any(marker.lower() in line.lower() for line in header_lines(path, 20))


def extract_python_docstring(path: Path) -> str | None:
    try:
        module = ast.parse(read_text(path))
    except SyntaxError:
        return None
    doc = ast.get_docstring(module)
    return first_doc_sentence(doc)


def first_doc_sentence(doc: str | None) -> str | None:
    if not doc:
        return None
    lines = [line.strip() for line in doc.strip().splitlines() if line.strip()]
    if not lines:
        return None
    if len(lines) > 1 and re.fullmatch(r"[A-Za-z0-9_.-]+\.(py|sh|ps1|bat|cmd)", lines[0]):
        return lines[1]
    return " ".join(lines[:2]) if len(lines[0]) < 40 and len(lines) > 1 else lines[0]


def extract_powershell_help(path: Path) -> str | None:
    lines = read_text(path).splitlines()
    for index, line in enumerate(lines):
        if line.strip().upper() == ".SYNOPSIS":
            collected: list[str] = []
            for next_line in lines[index + 1 :]:
                stripped = next_line.strip()
                if stripped.startswith(".") or stripped == "#>":
                    break
                if stripped:
                    collected.append(stripped)
            if collected:
                return " ".join(collected)
    return None


def extract_purpose_comment(path: Path) -> str | None:
    for line in header_lines(path):
        match = PURPOSE_RE.match(line)
        if match:
            return match.group(1)
    return None


def extract_help_description(path: Path) -> str | None:
    """Опитва да извлече описание от show_help heredoc при Bash/Batch-like скриптове."""
    text = read_text(path)
    patterns = [
        r"Описание:\s*\n(?P<body>(?:[ \t].+\n?)+)",
        r"DESCRIPTION\s*\n(?P<body>(?:[ \t].+\n?)+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        lines = [line.strip() for line in match.group("body").splitlines() if line.strip()]
        if lines:
            return lines[0]
    return None


def extract_description(path: Path) -> str:
    technology = detect_technology(path)
    description = extract_purpose_comment(path)
    if description:
        return description
    if technology == "Python":
        description = extract_python_docstring(path)
    elif technology == "PowerShell":
        description = extract_powershell_help(path)
    if not description:
        description = extract_help_description(path)
    if description:
        return description
    return "Няма извлечено описание. Стартирай help командата за повече информация."


def category_for_path(path: Path, repo_root: Path) -> tuple[str, str]:
    rel = path.relative_to(repo_root)
    parts = rel.parts
    if parts[0] == "tools" and len(parts) >= 4:
        category = "/".join(parts[1:-2])
        topic = parts[1]
        return category, topic
    if parts[0] == "bootstrap":
        return "bootstrap", "bootstrap"
    return parts[0], parts[0]


def help_command(command: str, technology: str) -> str:
    if technology == "PowerShell":
        return f"{command} -Help"
    if technology == "Batch/CMD":
        return f"{command} /?"
    return f"{command} --help"


def build_entry(path: Path, repo_root: Path) -> ScriptEntry:
    command = command_name_for_file(path)
    technology = detect_technology(path)
    category, topic = category_for_path(path, repo_root)
    entrypoint = has_marker(path, ENTRYPOINT_MARKER)
    no_path = has_marker(path, NO_PATH_MARKER)
    status = "active" if entrypoint and not no_path else "internal/no-path"
    rel_path = path.relative_to(repo_root).as_posix()
    return ScriptEntry(
        command=command,
        path=rel_path,
        category=category,
        topic=topic,
        technology=technology,
        platform=detect_platform(path, technology),
        status=status,
        entrypoint=entrypoint,
        no_path=no_path,
        description=extract_description(path),
        help_command=help_command(command, technology),
        markers=marker_list(path),
    )


def parse_removed_yaml(path: Path) -> list[RemovedEntry]:
    """Парсира простия YAML формат за removed-scripts.yaml без външна зависимост."""
    if not path.exists():
        return []
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "removed: []" or stripped == "removed:":
            continue
        if stripped.startswith("- "):
            if current is not None:
                entries.append(current)
            current = {}
            payload = stripped[2:]
            if ":" in payload:
                key, value = payload.split(":", 1)
                current[key.strip()] = value.strip().strip('"\'')
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip().strip('"\'')
    if current is not None:
        entries.append(current)

    result = []
    for item in entries:
        result.append(
            RemovedEntry(
                command=item.get("command", ""),
                path=item.get("path", ""),
                removed_at=item.get("removed_at", ""),
                replacement=item.get("replacement", ""),
                reason=item.get("reason", ""),
                purpose=item.get("purpose", ""),
            )
        )
    return result


def build_catalog(repo_root: Path, include_internal: bool = False) -> Catalog:
    entries = [build_entry(path, repo_root) for path in iter_script_files(repo_root)]
    if not include_internal:
        entries = [entry for entry in entries if entry.entrypoint and not entry.no_path]
    entries.sort(key=lambda item: (item.category, item.command, item.path))
    removed = parse_removed_yaml(repo_root / DEFAULT_REMOVED)
    # Генерираният JSON каталог не трябва да съдържа абсолютния локален път
    # на машината, от която е създаден. Всички script paths вече са относителни
    # спрямо repo root, затова тук пазим преносим маркер.
    return Catalog(".", entries, removed)


def catalog_to_dict(catalog: Catalog) -> dict:
    return {
        "repo_root": catalog.repo_root,
        "active": [asdict(entry) for entry in catalog.active],
        "removed": [asdict(entry) for entry in catalog.removed],
    }


def group_by_category(entries: Sequence[ScriptEntry]) -> dict[str, list[ScriptEntry]]:
    grouped: dict[str, list[ScriptEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.category, []).append(entry)
    return dict(sorted(grouped.items()))


def render_table(entries: Sequence[ScriptEntry]) -> str:
    rows = []
    grouped = group_by_category(entries)
    for category, category_entries in grouped.items():
        rows.append(category.upper())
        for entry in category_entries:
            rows.append(f"  {entry.command:<34} {entry.technology:<12} {entry.description}")
        rows.append("")
    return "\n".join(rows).rstrip()


def render_markdown(catalog: Catalog) -> str:
    lines = [
        "# Scripts Toolbox Catalog",
        "",
        "Автоматично генериран каталог на скриптовете в колекцията.",
        "",
        "## Как Да Ползваш Каталога",
        "",
        "- `scripts-catalog list` показва всички активни entrypoint скриптове.",
        "- `scripts-catalog search QUERY` търси по команда, описание, категория и път.",
        "- `scripts-catalog show COMMAND` показва подробности за конкретен скрипт.",
        "- `scripts-catalog help COMMAND` показва как да извикаш помощта на конкретен скрипт.",
        "- `scripts-catalog removed` показва архивираните/изтрити скриптове.",
        "",
        "## Активни Скриптове",
        "",
    ]
    for category, entries in group_by_category(catalog.active).items():
        lines.append(f"### {category}")
        lines.append("")
        lines.append("| Команда | Технология | Платформа | Описание | Помощ | Път |")
        lines.append("|---|---|---|---|---|---|")
        for entry in entries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        md_escape(entry.command),
                        md_escape(entry.technology),
                        md_escape(entry.platform),
                        md_escape(entry.description),
                        f"`{md_escape(entry.help_command)}`",
                        f"`{md_escape(entry.path)}`",
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.append("## Архив / Изтрити Скриптове")
    lines.append("")
    if not catalog.removed:
        lines.append("Няма регистрирани изтрити скриптове.")
    else:
        lines.append("| Команда | Изтрит на | Заместен от | Предназначение | Причина | Стар път |")
        lines.append("|---|---|---|---|---|---|")
        for item in catalog.removed:
            lines.append(
                "| "
                + " | ".join(
                    [
                        md_escape(item.command),
                        md_escape(item.removed_at),
                        md_escape(item.replacement),
                        md_escape(item.purpose),
                        md_escape(item.reason),
                        f"`{md_escape(item.path)}`",
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_generated_files(catalog: Catalog, repo_root: Path, markdown_path: Path, json_path: Path) -> None:
    markdown_target = resolve_repo_path(repo_root, markdown_path)
    json_target = resolve_repo_path(repo_root, json_path)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.write_text(render_markdown(catalog), encoding="utf-8")
    json_target.write_text(json.dumps(catalog_to_dict(catalog), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def filter_entries(
    entries: Sequence[ScriptEntry],
    *,
    category: str | None = None,
    technology: str | None = None,
    status: str | None = None,
) -> list[ScriptEntry]:
    result = list(entries)
    if category:
        result = [entry for entry in result if entry.category.startswith(category)]
    if technology:
        normalized = technology.lower()
        result = [entry for entry in result if entry.technology.lower() == normalized]
    if status:
        result = [entry for entry in result if entry.status == status]
    return result


def search_entries(entries: Sequence[ScriptEntry], query: str) -> list[ScriptEntry]:
    needle = query.lower()
    return [
        entry
        for entry in entries
        if needle in " ".join([entry.command, entry.path, entry.category, entry.technology, entry.description]).lower()
    ]


def find_entry(entries: Sequence[ScriptEntry], command: str) -> ScriptEntry | None:
    for entry in entries:
        if entry.command == command or Path(entry.path).stem == command:
            return entry
    return None


def print_entry(entry: ScriptEntry) -> None:
    print(f"Команда:      {entry.command}")
    print(f"Категория:    {entry.category}")
    print(f"Технология:   {entry.technology}")
    print(f"Платформа:    {entry.platform}")
    print(f"Статус:       {entry.status}")
    print(f"Път:          {entry.path}")
    print(f"Описание:     {entry.description}")
    print(f"Помощ:        {entry.help_command}")
    if entry.markers:
        print("Markers:")
        for marker in entry.markers:
            print(f"  - {marker}")


def run_help(entry: ScriptEntry, execute: bool) -> int:
    print(f"Помощ за {entry.command}:")
    print(f"  {entry.help_command}")
    if not execute:
        return 0
    command = entry.help_command.split()
    return subprocess.call(command)


def command_list(args: argparse.Namespace, catalog: Catalog) -> int:
    entries = filter_entries(catalog.active, category=args.category, technology=args.technology, status=args.status)
    if args.format == "json":
        print(json.dumps([asdict(entry) for entry in entries], ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(render_markdown(Catalog(catalog.repo_root, entries, [])))
    else:
        print(render_table(entries))
    return 0


def command_search(args: argparse.Namespace, catalog: Catalog) -> int:
    entries = search_entries(catalog.active, args.query)
    print(render_table(entries) if entries else "Няма намерени съвпадения.")
    return 0


def command_show(args: argparse.Namespace, catalog: Catalog) -> int:
    entry = find_entry(catalog.active, args.command)
    if not entry:
        print(f"Няма активен скрипт с команда: {args.command}", file=sys.stderr)
        return 1
    print_entry(entry)
    return 0


def command_help(args: argparse.Namespace, catalog: Catalog) -> int:
    entry = find_entry(catalog.active, args.command)
    if not entry:
        print(f"Няма активен скрипт с команда: {args.command}", file=sys.stderr)
        return 1
    return run_help(entry, execute=args.execute)


def command_removed(_: argparse.Namespace, catalog: Catalog) -> int:
    if not catalog.removed:
        print("Няма регистрирани изтрити скриптове.")
        return 0
    for item in catalog.removed:
        print(f"{item.command} ({item.removed_at})")
        print(f"  Стар път:       {item.path}")
        print(f"  Заместен от:    {item.replacement or '-'}")
        print(f"  Предназначение: {item.purpose or '-'}")
        print(f"  Причина:        {item.reason or '-'}")
    return 0


def command_stats(_: argparse.Namespace, catalog: Catalog) -> int:
    by_technology: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for entry in catalog.active:
        by_technology[entry.technology] = by_technology.get(entry.technology, 0) + 1
        by_category[entry.category] = by_category.get(entry.category, 0) + 1
    print(f"Активни скриптове: {len(catalog.active)}")
    print(f"Архивирани скриптове: {len(catalog.removed)}")
    print("\nПо технология:")
    for key, value in sorted(by_technology.items()):
        print(f"  {key}: {value}")
    print("\nПо категория:")
    for key, value in sorted(by_category.items()):
        print(f"  {key}: {value}")
    return 0


def command_generate(args: argparse.Namespace, catalog: Catalog, repo_root: Path) -> int:
    write_generated_files(catalog, repo_root, Path(args.markdown), Path(args.json))
    print(f"Генериран Markdown: {resolve_repo_path(repo_root, Path(args.markdown))}")
    print(f"Генериран JSON:     {resolve_repo_path(repo_root, Path(args.json))}")
    return 0


def command_validate(args: argparse.Namespace, catalog: Catalog, repo_root: Path) -> int:
    markdown_path = resolve_repo_path(repo_root, Path(args.markdown))
    json_path = resolve_repo_path(repo_root, Path(args.json))
    expected_md = render_markdown(catalog)
    expected_json = json.dumps(catalog_to_dict(catalog), ensure_ascii=False, indent=2) + "\n"
    problems = []
    if not markdown_path.exists() or markdown_path.read_text(encoding="utf-8") != expected_md:
        problems.append(str(markdown_path))
    if not json_path.exists() or json_path.read_text(encoding="utf-8") != expected_json:
        problems.append(str(json_path))
    if problems:
        print("Каталогът не е актуален. Генерирай го с: scripts-catalog generate", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("Каталогът е актуален.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts-catalog",
        description="Енциклопедичен каталог и генератор за scripts-toolbox.",
    )
    parser.add_argument("--repo-root", help="Repo root. По подразбиране се открива автоматично.")
    parser.add_argument("--include-internal", action="store_true", help="Включва no-path/internal скриптове в активния изглед.")
    sub = parser.add_subparsers(dest="command_name", required=True)

    list_parser = sub.add_parser("list", help="Показва активните скриптове по категории.")
    list_parser.add_argument("-c", "--category", help="Филтър по категория, например media/audio.")
    list_parser.add_argument("-t", "--technology", help="Филтър по технология: Python, Bash, PowerShell, Batch/CMD.")
    list_parser.add_argument("--status", help="Филтър по статус.")
    list_parser.add_argument("-f", "--format", choices=("table", "json", "markdown"), default="table")

    search_parser = sub.add_parser("search", help="Търси в командите, пътищата, категориите и описанията.")
    search_parser.add_argument("query")

    show_parser = sub.add_parser("show", help="Показва подробности за команда.")
    show_parser.add_argument("command")

    help_parser = sub.add_parser("help", help="Показва help командата за конкретен скрипт.")
    help_parser.add_argument("command")
    help_parser.add_argument("-x", "--execute", action="store_true", help="Изпълнява help командата вместо само да я покаже.")

    generate_parser = sub.add_parser("generate", help="Генерира Markdown и JSON каталог.")
    generate_parser.add_argument("--markdown", default=str(DEFAULT_MARKDOWN))
    generate_parser.add_argument("--json", default=str(DEFAULT_JSON))

    validate_parser = sub.add_parser("validate", help="Проверява дали генерираният каталог е актуален.")
    validate_parser.add_argument("--markdown", default=str(DEFAULT_MARKDOWN))
    validate_parser.add_argument("--json", default=str(DEFAULT_JSON))

    sub.add_parser("removed", help="Показва архивираните/изтрити скриптове.")
    sub.add_parser("stats", help="Показва статистика по категории и технологии.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = find_repo_root(Path(args.repo_root) if args.repo_root else Path.cwd())
    catalog = build_catalog(repo_root, include_internal=args.include_internal)

    if args.command_name == "list":
        return command_list(args, catalog)
    if args.command_name == "search":
        return command_search(args, catalog)
    if args.command_name == "show":
        return command_show(args, catalog)
    if args.command_name == "help":
        return command_help(args, catalog)
    if args.command_name == "generate":
        return command_generate(args, catalog, repo_root)
    if args.command_name == "validate":
        return command_validate(args, catalog, repo_root)
    if args.command_name == "removed":
        return command_removed(args, catalog)
    if args.command_name == "stats":
        return command_stats(args, catalog)
    parser.error(f"Непозната команда: {args.command_name}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
