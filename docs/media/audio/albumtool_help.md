# albumtool.py - помощник с примери

`albumtool.py` обработва аудио албуми в директории:

- разпознава изпълнител и албум от името на директорията;
- търси metadata в избрана база;
- сравнява локалните файлове с траклиста;
- преименува файловете в правилен ред;
- записва metadata чрез `ffmpeg` без прекодиране;
- генерира и вгражда chapters за single-file албуми.

## Източници на metadata

Източникът се избира с `-S`:

```bash
-S itunes
-S discogs
-S musicbrainz
```

Практическа препоръка:

```text
itunes      добър първи избор за комерсиални албуми и точни durations
discogs     добър за физически издания, labels, catalog numbers
musicbrainz добър за отворени metadata и MusicBrainz IDs
```

## Основен принцип

Първо винаги проверявай с `scan`:

```bash
albumtool.py -S itunes scan -d '<album-dir>'
```

После пускай реалната операция първо с `--dry-run`:

```bash
albumtool.py -S itunes all -d '<album-dir>' --dry-run
```

И чак след това без `--dry-run`:

```bash
albumtool.py -S itunes all -d '<album-dir>'
```

## `rename` срещу `tag`

`rename` и `tag` имат различни задачи.

`rename`:

- променя имената на файловете;
- добавя правилен track номер отпред;
- премахва шум от имена, например YouTube тагове;
- помага за правилно сортиране в директорията.

`tag`:

- записва metadata вътре в аудио файловете;
- използва `ffmpeg`;
- не прекодира аудиото;
- помага на Lexus infotainment, Android Auto и други плеъри да показват правилно artist, album, title, track number.

За нормална multi-file обработка използвай `run-all` или съкратено `all`, защото прави първо `rename`, после `tag`.

## Multi-File албум

Албумът е директория с много отделни аудио файлове.

Пример:

```bash
albumtool.py -S itunes scan -d './Acappella - (2002) Live from Paris'
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris' --dry-run
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris'
```

Пълното име на командата е `run-all`:

```bash
albumtool.py -S itunes run-all -d './Acappella - (2002) Live from Paris'
```

Съкратеното име е `all`:

```bash
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris'
```

## Само преименуване

Използвай това, когато искаш да провериш или коригираш само имената на файловете.

```bash
albumtool.py -S itunes rename -d './Acappella - (2002) Live from Paris' --dry-run
albumtool.py -S itunes rename -d './Acappella - (2002) Live from Paris'
```

## Само metadata tagging

Използвай това, когато имената вече са правилни, но metadata липсват или са грешни.

```bash
albumtool.py -S itunes tag -d './Acappella - (2002) Live from Paris' --dry-run
albumtool.py -S itunes tag -d './Acappella - (2002) Live from Paris'
```

## Добавяне на обложка

Обложката се подава с `-C`.

```bash
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris' -C cover.jpg --dry-run
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris' -C cover.jpg
```

Това не изтегля обложка. Файлът трябва вече да съществува.

`-C` има приоритет пред `--auto-cover`.

## Изтегляне на обложка

Командата `cover` изтегля обложка от metadata източника, ако в директорията няма локална обложка.

Съкратено име:

```bash
albumtool.py -S itunes cov -d './Album' -n
```

Пълно име:

```bash
albumtool.py -S itunes cover -d './Album' -n
```

Реално изтегляне:

```bash
albumtool.py -S itunes cover -d './Album'
```

Ако вече има `cover.jpg`, `folder.jpg`, `front.jpg` или `album.jpg`, командата няма да тегли нова обложка.

За принудително изтегляне:

```bash
albumtool.py -S itunes cover -d './Album' --force
```

## Автоматично използване на локална обложка

`--auto-cover` не тегли обложка. То само търси локален файл:

```text
cover.jpg
folder.jpg
front.jpg
album.jpg
```

и го използва при `tag`, `all` или `embed-chapters -T`.

Пример:

```bash
albumtool.py -S itunes cover -d './Album'
albumtool.py -S itunes all -d './Album' --auto-cover -n
albumtool.py -S itunes all -d './Album' --auto-cover
```

Ако искаш да посочиш конкретна обложка:

```bash
albumtool.py -S itunes all -d './Album' -C './my-cover.jpg'
```

## Цяла директория на изпълнител

Ако си в директорията на изпълнителя:

```text
/mnt/usb/Music/Acappella
```

можеш да обработиш всички album директории вътре:

```bash
albumtool.py -S itunes scan -d .
albumtool.py -S itunes all -d . --dry-run
albumtool.py -S itunes all -d .
```

## Само един албум от директория на изпълнител

Използвай `-O` / `--album-only`.

```bash
albumtool.py -S itunes all -d . -O 'Live from Paris' --dry-run
albumtool.py -S itunes all -d . -O 'Live from Paris'
```

## Само няколко албума

`-O` може да се подаде повече от веднъж.

```bash
albumtool.py -S itunes all -d . -O 'Live from Paris' -O 'Classycal' --dry-run
albumtool.py -S itunes all -d . -O 'Live from Paris' -O 'Classycal'
```

## Преименуване на album директории

Командата `rename-dirs` преименува директориите на албумите според metadata от избрания източник.

Съкратено име:

```bash
albumtool.py -S itunes dirs -d '<artist-dir>' -n
```

Пълно име:

```bash
albumtool.py -S itunes rename-dirs -d '<artist-dir>' -n
```

Винаги започвай с `-n` / `--dry-run`.

### Шаблони за директории

Шаблонът се избира с `-D` / `--dir-template`.

```text
year-title                 1994-Classycal
year-spaced-title          1994 - Classycal
artist-year-title          Acappella - 1994-Classycal
artist-year-spaced-title   Acappella - 1994 - Classycal
```

За artist-root структура:

```text
Music/
  Acappella/
    1994-Classycal/
    2002-Live from Paris/
```

използвай:

```bash
albumtool.py -S itunes dirs -d ./Acappella -D year-title -n
albumtool.py -S itunes dirs -d ./Acappella -D year-title
```

За mixed-root структура:

```text
Music/
  Acappella/
    Acappella - ...
    Glad - ...
    Take 6 - ...
```

използвай шаблон с artist:

```bash
albumtool.py -S itunes dirs -d ./Acappella -D artist-year-title -n
albumtool.py -S itunes dirs -d ./Acappella -D artist-year-title
```

### Защити при `rename-dirs`

`rename-dirs` прескача директория, ако:

- избраният provider не намери релийз;
- намереният релийз има твърде различно album title;
- текущото име съдържа година и provider-ът връща различна година;
- целевата директория вече съществува;
- повече от една директория води до едно и също целево име.

Прагът за сходство между текущ album title и намерения релийз се задава с `-R`.

```bash
albumtool.py -S itunes dirs -d ./Acappella -D artist-year-title -R 0.80 -n
```

По подразбиране:

```text
-R 0.75
```

## Праг за съвпадение между файл и трак

Прагът се задава с `-M`.

```bash
albumtool.py -S itunes rename -d './Album' -M 0.75 --dry-run
```

Примерни стойности:

```text
0.55  по-либерално съвпадение
0.75  балансирано съвпадение
0.85  по-строго съвпадение
```

Ако локалните имена са шумни или идват от YouTube, започни с `0.55` или `0.65`.

## Single-File албум

Single-file албум е един аудио файл, който съдържа целия албум.

Първо генерирай chapter файл:

```bash
albumtool.py -S itunes chapters -d './Acappella - (2002) Live from Paris'
```

Съкратено:

```bash
albumtool.py -S itunes ch -d './Acappella - (2002) Live from Paris'
```

Това създава:

```text
chapters.txt
```

След това прегледай и редактирай началата на главите, ако е нужно.

## Вграждане на chapters

Първо dry-run:

```bash
albumtool.py -S itunes embed-chapters -d './Acappella - (2002) Live from Paris' --dry-run
```

После реално вграждане:

```bash
albumtool.py -S itunes embed-chapters -d './Acappella - (2002) Live from Paris'
```

Съкратени варианти:

```bash
albumtool.py -S itunes embed -d './Album'
albumtool.py -S itunes ech -d './Album'
```

## Single-File албум с metadata и обложка

`-T` записва album-level metadata в единичния аудио файл.

```bash
albumtool.py -S itunes ech -d './Album' -T -C cover.jpg --dry-run
albumtool.py -S itunes ech -d './Album' -T -C cover.jpg
```

С автоматично използване на локална обложка:

```bash
albumtool.py -S itunes ech -d './Album' -T --auto-cover --dry-run
albumtool.py -S itunes ech -d './Album' -T --auto-cover
```

## Backup поведение

По подразбиране реалните операции създават backup.

За да зададеш директория:

```bash
albumtool.py -S itunes all -d './Album' --backup-dir './_backup_album'
```

За да изключиш backup:

```bash
albumtool.py -S itunes all -d './Album' --no-backup
```

`--no-backup` не се препоръчва, освен ако работиш върху копие.

## Практически workflows

### Най-чест workflow за един multi-file албум

```bash
albumtool.py -S itunes scan -d '<album-dir>'
albumtool.py -S itunes all -d '<album-dir>' --dry-run
albumtool.py -S itunes all -d '<album-dir>'
```

### Пълен workflow за artist-root директория

Ако директорията съдържа само албуми на един изпълнител:

```bash
albumtool.py -S itunes dirs -d '<artist-dir>' -D year-title -n
albumtool.py -S itunes dirs -d '<artist-dir>' -D year-title
albumtool.py -S itunes all -d '<artist-dir>' -n
albumtool.py -S itunes all -d '<artist-dir>'
```

### Пълен workflow за mixed-root директория

Ако директорията съдържа албуми на различни изпълнители:

```bash
albumtool.py -S itunes dirs -d '<mixed-dir>' -D artist-year-title -n
albumtool.py -S itunes dirs -d '<mixed-dir>' -D artist-year-title
albumtool.py -S itunes all -d '<mixed-dir>' -n
albumtool.py -S itunes all -d '<mixed-dir>'
```

### Ако iTunes не намери албума

```bash
albumtool.py -S discogs scan -d '<album-dir>'
albumtool.py -S musicbrainz scan -d '<album-dir>'
```

После използвай източника, който намери най-точния резултат:

```bash
albumtool.py -S discogs all -d '<album-dir>' --dry-run
albumtool.py -S discogs all -d '<album-dir>'
```

### Ако Discogs не намери албума, но iTunes го намира

```bash
albumtool.py -S itunes scan -d '<album-dir>'
albumtool.py -S itunes all -d '<album-dir>' --dry-run
albumtool.py -S itunes all -d '<album-dir>'
```

## Бърза справка

```text
scan                 проверка, не променя файлове
rename               само преименува файлове
tag                  само записва metadata
run-all / all        преименува и тагва multi-file албум
rename-dirs / dirs   преименува album директории
cover / cov          изтегля локална обложка от metadata източника
chapters / ch        генерира chapters.txt за single-file албум
embed-chapters       вгражда chapters
embed / ech          съкратени имена за embed-chapters
```
