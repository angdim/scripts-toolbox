# scripts-toolbox

Лична, но структурирана и готова за GitHub колекция от Linux/Windows скриптове за автоматизация, media обработка, текстови операции, работа с файлове и помощни инструменти.

Основната цел на репото е да държи на едно място самостоятелни скриптове, по-големи Python пакети, bootstrap инструменти и документация, без да се замърсява системният `PATH` с много директории. Вместо това скриптовете се публикуват като команди чрез symlink-и или wrapper-и в една целева директория, например `~/bin`.

## Какво съдържа

Към момента каталогът открива:

- 37 активни скрипта.
- 17 Python скрипта.
- 13 Bash скрипта.
- 6 PowerShell скрипта.
- 1 Batch/CMD скрипт.

Основни категории:

- `media/audio` - аудио обработка, EQ, peak normalization, конвертиране, playlist-и.
- `media/video` - видео конвертиране, split по време, профили за устройства.
- `media/speech` - разпознаване, разделяне по говорител, speech/audio workflows.
- `text/transcript` - обработка на транскрипти и говорители.
- `files/duplicates` - търсене и анализ на дублирани файлове.
- `files/names` - нормализиране на имена на файлове и директории.
- `catalog` - автоматичен каталог на самата колекция.
- `bootstrap` - инсталиране на команден достъп до скриптовете.

Пълният актуален списък е в [docs/catalog/scripts-catalog.md](docs/catalog/scripts-catalog.md).

## Структура на репото

```text
bootstrap/   Скриптове за публикуване на командите в системата.
tools/       Самостоятелни потребителски скриптове, групирани по цел и технология.
packages/    По-големи пакети и reusable код, използван от инструменти.
docs/        Документация, каталог, testing notes и архитектурни бележки.
examples/    Примерни входове, команди и сценарии.
samples/     Локални/demo media файлове; големите файлове не се качват в git.
tests/       Unit, integration, e2e, Bash и PowerShell тестове.
archive/     Стари, заменени или експериментални скриптове за справка.
```

Избраната организация е хибридна:

```text
tools/<domain>/<subdomain>/<technology>/
packages/<language>/<package>/
bootstrap/<platform>/
```

Така целта на скрипта е водеща, а технологията е последното ниво. Това позволява да съществуват паралелни Bash/Python/PowerShell реализации на една и съща задача, без да се губи тематичната подредба.

Подробности: [docs/repo/repo_structure.md](docs/repo/repo_structure.md).

## Бърз старт под Linux

Клониране:

```bash
git clone https://github.com/<your-user>/scripts-toolbox.git ~/scripts
cd ~/scripts
```

Създаване на Python среда за тестове и Python инструменти:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

Публикуване на командите в `~/bin`:

```bash
bash bootstrap/linux/install-to-path.sh --clean --all --source ~/scripts --target ~/bin
```

Ако използваш вече установения локален скрипт в home директорията:

```bash
~/add-scripts-to-path.sh --clean -a ~/scripts
```

Провери дали `~/bin` е в `PATH`:

```bash
echo "$PATH" | tr ':' '\n' | grep -x "$HOME/bin"
```

Ако липсва, добави го:

```bash
grep -qxF 'export PATH="$HOME/bin:$PATH"' ~/.bashrc || echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Проверка:

```bash
command -v scripts-catalog
scripts-catalog stats
```

## Бърз старт под Windows

В PowerShell:

```powershell
git clone https://github.com/<your-user>/scripts-toolbox.git $HOME\scripts
cd $HOME\scripts
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Публикуване на командите като `.cmd` wrapper-и:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\windows\Install-ToPath.ps1 -Source . -Target "$HOME\bin" -All
```

Увери се, че `$HOME\bin` е в потребителския `PATH`.

## Каталог на скриптовете

Репото съдържа енциклопедичен каталог, който се генерира автоматично от наличните скриптове и техните маркери, help текстове и metadata.

Основен инструмент:

```bash
scripts-catalog
```

Ако командите още не са публикувани в `PATH`, използвай директно:

```bash
tools/catalog/python/scripts_catalog.py
```

Полезни команди:

```bash
scripts-catalog stats
scripts-catalog list
scripts-catalog list -c media/audio
scripts-catalog list -t Python
scripts-catalog search normalize
scripts-catalog show audio_peak_eq
scripts-catalog help audio_peak_eq
scripts-catalog help audio_peak_eq --execute
scripts-catalog generate
scripts-catalog validate
scripts-catalog removed
```

Формати за списъци:

```bash
scripts-catalog list --format table
scripts-catalog list --format markdown
scripts-catalog list --format json
```

Генерирани файлове:

- [docs/catalog/scripts-catalog.md](docs/catalog/scripts-catalog.md) - четим каталог за GitHub.
- [docs/catalog/scripts-catalog.json](docs/catalog/scripts-catalog.json) - машинно четим каталог.
- [docs/catalog/removed-scripts.yaml](docs/catalog/removed-scripts.yaml) - архив на премахнати скриптове.

Документация: [docs/catalog/README.md](docs/catalog/README.md).

## Как работи публикуването на команди

Инсталаторите не публикуват всеки файл автоматично. Публикуват се само скриптове, маркирани като entrypoint.

Минимален маркер:

```text
scripts-toolbox: entrypoint
```

Скрипт, който не трябва да се публикува:

```text
scripts-toolbox: no-path
```

Явно име на команда:

```text
scripts-toolbox: command=my_command_name
```

Това е по-надеждно от ограничаване по дълбочина, защото директориите могат да растат, а помощните файлове могат да са на различни нива.

Пример за Python:

```python
#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# scripts-toolbox: command=example-tool
```

Пример за Bash:

```bash
#!/usr/bin/env bash
# scripts-toolbox: entrypoint
# scripts-toolbox: command=example-tool
```

## Linux bootstrap

Dry run:

```bash
bash bootstrap/linux/install-to-path.sh --all --dry-run --source ~/scripts --target ~/bin
```

Пълно обновяване:

```bash
bash bootstrap/linux/install-to-path.sh --clean --all --source ~/scripts --target ~/bin
```

Само Python скриптове:

```bash
bash bootstrap/linux/install-to-path.sh --python --source ~/scripts --target ~/bin
```

Само Bash скриптове:

```bash
bash bootstrap/linux/install-to-path.sh --bash --source ~/scripts --target ~/bin
```

## Windows bootstrap

Dry run:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\windows\Install-ToPath.ps1 -Source . -Target "$HOME\bin" -All -DryRun
```

Пълно обновяване:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\windows\Install-ToPath.ps1 -Source . -Target "$HOME\bin" -All -Clean
```

## Добавяне на нов скрипт

1. Избери правилната тематична директория под `tools/`.
2. Избери технологията като последно ниво: `python`, `bash`, `powershell`, `windows`, `lua`, `perl` и т.н.
3. Добави shebang, ако платформата го изисква.
4. Добави `scripts-toolbox: entrypoint`, ако скриптът трябва да стане команда.
5. Добави `scripts-toolbox: no-path`, ако е помощен файл.
6. Добави `scripts-toolbox: command=...`, ако автоматичното име не е достатъчно ясно или има конфликт.
7. Добави help/usage текст на български.
8. Добави тестове според технологията.
9. Обнови каталога.

Примерна структура:

```text
tools/media/audio/python/new_audio_tool.py
tools/media/audio/bash/new_audio_tool.sh
tools/files/names/powershell/Rename-Files.ps1
```

След добавяне:

```bash
scripts-catalog generate
scripts-catalog validate
.venv/bin/python -m pytest -q
```

## Изисквания към качеството

За потребителски скриптове:

- Ясно предназначение в началния коментар или docstring.
- Help функция или CLI `--help`.
- Предвидими exit кодове.
- Разбираеми грешки при липсващи зависимости.
- Без скрити destructive операции без потвърждение или dry-run режим.
- Ясно разделение между самостоятелни entrypoint скриптове и помощни модули.

За Python:

- `argparse` за CLI инструменти.
- `subprocess.run(..., check=False/True)` с ясна обработка на грешки.
- Unit тестове за чистата логика.
- Integration/e2e тестове за реални CLI сценарии.
- `ruff` и `mypy` без грешки.

За Bash:

- `set -euo pipefail`, когато е приложимо.
- Quote-нати променливи.
- `shellcheck` без критични предупреждения.
- `bash -n` проверка.
- Dry-run при операции върху файлове, когато е разумно.

За PowerShell:

- `CmdletBinding()` при по-сложни скриптове.
- Ясни параметри и help блок.
- Parser check и Pester тестове.

## Тестове

Стандартни тестове:

```bash
.venv/bin/python -m pytest -q
```

E2E тестове:

```bash
.venv/bin/python -m pytest -q -m e2e
```

Python static checks:

```bash
.venv/bin/ruff check tools packages tests --exclude '*/.venv/*' --exclude '__pycache__'
PYFILES=$(find tools packages tests -type f -name '*.py' -not -path '*/.venv/*' -not -path '*/__pycache__/*' | tr '\n' ' ')
.venv/bin/mypy $PYFILES
```

Bash checks:

```bash
shellcheck $(find tools bootstrap -type f -name '*.sh' -not -path '*/.venv/*' | sort)
for f in $(find tools bootstrap -type f -name '*.sh' -not -path '*/.venv/*' | sort); do bash -n "$f"; done
```

PowerShell/Pester:

```bash
pwsh -NoProfile -Command "Invoke-Pester -Path tests/powershell -CI"
```

Подробности: [docs/testing.md](docs/testing.md).

## CI

GitHub Actions workflow:

```text
.github/workflows/ci.yml
```

Покрива:

- Linux Python тестове.
- Bash syntax и shellcheck.
- Python `ruff` и `mypy`.
- Проверка дали каталогът е актуален.
- Windows PowerShell parser/Pester проверки.
- Ръчни e2e тестове чрез `workflow_dispatch`.

## Зависимости

Основни системни инструменти, според използваните скриптове:

- `python3`
- `bash`
- `ffmpeg` и `ffprobe`
- `shellcheck`
- `pwsh` за PowerShell тестове под Linux
- `git`
- `ripgrep`/`rg`

Python зависимости:

```bash
pip install -r requirements.txt
```

Dev/test зависимости:

```bash
pip install -r requirements-dev.txt
```

Някои инструменти имат специфични runtime зависимости. Проверявай `--help` на конкретния скрипт или записа му в каталога.

## Архивиране и премахване на скриптове

Когато скрипт бъде премахнат или заменен, добави запис в:

```text
docs/catalog/removed-scripts.yaml
```

Пример:

```yaml
removed:
  - command: old_audio_normalizer
    path: tools/media/audio/python/old_audio_normalizer.py
    removed_at: 2026-06-13
    replacement: audio_peak_eq
    reason: "Заменен от по-пълен инструмент."
    purpose: "Peak normalization на аудио файлове."
```

След това:

```bash
scripts-catalog generate
scripts-catalog validate
```

## Git workflow

Преди commit:

```bash
scripts-catalog generate
scripts-catalog validate
.venv/bin/python -m pytest -q
.venv/bin/ruff check tools packages tests --exclude '*/.venv/*' --exclude '__pycache__'
```

Примерно първоначално качване към GitHub:

```bash
cd ~/scripts
git init
git add .
git commit -m "Initial scripts-toolbox structure"
git branch -M main
git remote add origin https://github.com/<your-user>/scripts-toolbox.git
git push -u origin main
```

Ако използваш GitHub CLI:

```bash
cd ~/scripts
gh repo create scripts-toolbox --private --source=. --remote=origin --push
```

Смени `--private` с `--public`, ако искаш публично репо.

## Лиценз

Добави `LICENSE` файл преди публично публикуване, ако репото ще бъде public. За лична употреба може да остане private без лиценз, но за публично споделяне е добре да избереш ясен лиценз, например MIT, Apache-2.0 или GPL-3.0.
