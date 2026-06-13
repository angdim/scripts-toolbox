# Тестове и CI

Този repo използва единна pytest рамка за Python, Bash, PowerShell и media integration тестове.

## Локални команди

Бързият стандартен набор изключва `slow`, `e2e` и `network` тестове чрез `pyproject.toml`:

```bash
.venv/bin/python -m pytest -q
```

Пускане на slow/e2e media тестове:

```bash
.venv/bin/python -m pytest -q -m e2e
```

Static quality gates:

```bash
.venv/bin/ruff check tools packages tests --exclude '*/.venv/*' --exclude '__pycache__'
PYFILES=$(find tools packages tests -type f -name '*.py' -not -path '*/.venv/*' -not -path '*/__pycache__/*' | tr '\n' ' ')
.venv/bin/mypy $PYFILES
shellcheck $(find tools bootstrap -type f -name '*.sh' -not -path '*/.venv/*' | sort)
for f in $(find tools bootstrap -type f -name '*.sh' -not -path '*/.venv/*' | sort); do bash -n "$f"; done
```

PowerShell/Pester:

```bash
pwsh -NoProfile -Command "Invoke-Pester -Path tests/powershell -CI"
```

## Pytest markers

- `unit`: бързи unit тестове.
- `integration`: тестове, които изпълняват скриптове или локални инструменти.
- `e2e`: пълни end-to-end сценарии.
- `media`: тестове, които генерират или обработват audio/video чрез FFmpeg.
- `slow`: умишлено по-бавни тестове, изключени по подразбиране.
- `network`: реална мрежа; по подразбиране не се пуска.
- `linux`: Linux-specific сценарии.
- `windows`: Windows-specific сценарии.
- `powershell`: PowerShell/Pester сценарии.

## GitHub Actions

Workflow: `.github/workflows/ci.yml`

- Linux job: Python, Bash, FFmpeg/media tests и static checks.
- Windows job: PowerShell parser, Pester и Windows/PowerShell pytest subset.
- E2E тестовете се пускат ръчно чрез `workflow_dispatch` с `run_e2e=true`.
