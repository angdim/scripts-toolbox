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

`-S` е задължителен само за команди, които реално търсят или изтеглят metadata:
`scan`, `dirs`, `cover`, `chapters` и `embed-chapters -T`.

`rename`, `tag` и `run-all` могат да работят по два начина:

- с `-S` - теглят track metadata от избрания източник;
- без `-S` - работят offline и извличат заглавията от текущите имена на файловете.

`embed-chapters` без `-T` и `split-sfa` работят offline с вече наличен chapter файл и не изискват `-S`.

## Основен принцип

Първо винаги проверявай с `scan`:

```bash
albumtool.py -S itunes scan -d '<album-dir>'
```

За single-file албум, подаден директно като файл:

```bash
albumtool.py -S itunes scan -F './Artist - 2024 - Album.m4a'
```

За групова проверка на няколко SFA файла в една директория:

```bash
albumtool.py -S itunes scan --sfa-glob './*.m4a'
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

Ако албумът липсва в metadata базите, но файловете са коректно номерирани и именувани, пропусни `-S`.
Тогава `rename`, `tag` и `run-all` използват реда на файловете и заглавията от имената им.

## Multi-File албум

Албумът е директория с много отделни аудио файлове.

Пример:

```bash
albumtool.py -S itunes scan -d './Acappella - (2002) Live from Paris'
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris' --dry-run
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris'
```

Offline обработка без външна metadata база:

```bash
albumtool.py all -d './Audio Book Album' -a 'Author Name' -A 'Book Title' --dry-run
albumtool.py all -d './Audio Book Album' -a 'Author Name' -A 'Book Title'
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

Offline вариант от текущите имена на файловете:

```bash
albumtool.py rn -d './Audio Book Album' -a 'Author Name' -A 'Book Title' -n
albumtool.py rn -d './Audio Book Album' -a 'Author Name' -A 'Book Title'
```

## Само metadata tagging

Използвай това, когато имената вече са правилни, но metadata липсват или са грешни.

```bash
albumtool.py -S itunes tag -d './Acappella - (2002) Live from Paris' --dry-run
albumtool.py -S itunes tag -d './Acappella - (2002) Live from Paris'
```

Offline вариант от текущите имена на файловете:

```bash
albumtool.py tg -d './Audio Book Album' -a 'Author Name' -A 'Book Title' -n
albumtool.py tg -d './Audio Book Album' -a 'Author Name' -A 'Book Title'
```

## Добавяне на обложка

Обложката се подава с `-C`.

```bash
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris' -C cover.jpg --dry-run
albumtool.py -S itunes all -d './Acappella - (2002) Live from Paris' -C cover.jpg
```

Това не изтегля обложка. Файлът трябва вече да съществува.

`-C` има приоритет пред `--auto-cover`.

## Cover профили за Lexus / Android Auto

`-P` / `--cover-profile` задава как да се подготви обложката преди вграждане.

Налични профили:

```text
source           използва подадената обложка без промяна
lexus-jpeg-300  създава embedded JPEG 300x300
lexus-jpeg-500  създава embedded JPEG 500x500
```

Реалният тест с Lexus RX 450h 2017 показа:

- `USB cover art by Gracenote®` трябва да е изключено, за да се показват локалните embedded обложки;
- JPEG 300x300 и JPEG 500x500 се показват коректно;
- визуално 300x300 и 500x500 нямат съществена разлика на заводския дисплей;
- PNG 500x500 не е надежден и не е включен като Lexus-safe профил.

Препоръчителен профил:

```bash
albumtool.py -S itunes all -d './Album' -C cover.jpg -P lexus-jpeg-500 --dry-run
albumtool.py -S itunes all -d './Album' -C cover.jpg -P lexus-jpeg-500
```

Консервативен fallback:

```bash
albumtool.py -S itunes all -d './Album' -C cover.jpg -P lexus-jpeg-300
```

## Изтегляне на обложка

Командата `cover` изтегля обложка от metadata източника, ако в директорията няма локална обложка.
Името на изтегления файл се базира на името на албума в безопасен файлов формат, например:

```text
God_Is_Able.jpg
```

Съкратено име:

```bash
albumtool.py -S itunes cov -d './Album' -n
```

Dry-run режимът не записва файл. Той показва:

- всички локални image кандидати;
- всички remote cover кандидати от metadata;
- формат на изображението;
- размери в пиксели;
- файлов размер;
- целево име за запис при remote кандидатите.

Пълно име:

```bash
albumtool.py -S itunes cover -d './Album' -n
```

Реално изтегляне:

```bash
albumtool.py -S itunes cover -d './Album'
```

Ако metadata източникът връща няколко обложки, първо виж номерата им:

```bash
albumtool.py -S discogs cover -d './Album' -n
```

После избери конкретна remote обложка по 1-базиран индекс:

```bash
albumtool.py -S discogs cover -d './Album' --cover-index 2
```

Ако вече има `cover.jpg`, `folder.jpg`, `front.jpg`, `album.jpg` или само един image файл в директорията, командата няма да тегли нова обложка.

За принудително изтегляне:

```bash
albumtool.py -S itunes cover -d './Album' --force
albumtool.py -S discogs cover -d './Album' --cover-index 2 --force
```

## Автоматично използване на локална обложка

`--auto-cover` не тегли обложка. То само търси локален файл:

```text
cover.jpg
folder.jpg
front.jpg
album.jpg
God_Is_Able.jpg  # ако това е единственият image файл в директорията
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

По подразбиране файлът е в човешки четим `human` формат:

```text
# albumtool chapters format: human-v1
# Редактирай заглавието и началния момент под него във формат HH:MM:SS.mmm.

Right Here Right Now (Live)
00:00:00.000

Send It on Down (Live)
00:04:00.000
```

След това прегледай и редактирай началата на главите, ако е нужно.

Timestamp форматът е `HH:MM:SS.mmm`, например `00:21:18.030`.
Ако по навик запишеш `00:21:18:030`, инструментът ще го нормализира автоматично до `00:21:18.030`.

Ако по някаква причина ти трябва старият FFmpeg/OGM формат:

```bash
albumtool.py -S itunes chapters -d './Album' --chapters-format ogm
```

`embed-chapters` разпознава автоматично и двата формата. Human файлът се конвертира временно до OGM само за подаване към FFmpeg.

### Direct SFA режим

Ако няколко single-file албума са в една директория, не е задължително всеки да бъде в отделна album директория.
Използвай explicit SFA вход:

```bash
albumtool.py -S itunes chapters -F './Ron Kenoly - 1993 - God Is Able.m4a'
```

За групова обработка:

```bash
albumtool.py -S itunes chapters --sfa-glob './*.m4a'
```

В direct SFA режим artist/album се извличат от името на файла, например:

```text
Ron Kenoly - 1993 - God Is Able.m4a
```

Ако името не е достатъчно ясно, задай ги ръчно:

```bash
albumtool.py -S itunes chapters -F './God Is Able.m4a' --artist 'Ron Kenoly' --album 'God Is Able'
```

По подразбиране direct SFA режимът създава sidecar файл:

```text
<audio-stem>.chapters.txt
```

Например:

```text
Ron Kenoly - 1993 - God Is Able.chapters.txt
```

Може да се използва template `{stem}`:

```bash
albumtool.py -S itunes chapters --sfa-glob './*.m4a' -o '{stem}.chapters.txt'
```

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

Direct SFA режим с автоматичен sidecar `<audio-stem>.chapters.txt`:

```bash
albumtool.py -S itunes ech -F './Ron Kenoly - 1993 - God Is Able.m4a' --dry-run
albumtool.py -S itunes ech -F './Ron Kenoly - 1993 - God Is Able.m4a'
```

Групово, in-place:

```bash
albumtool.py -S itunes ech --sfa-glob './*.m4a' --dry-run
albumtool.py -S itunes ech --sfa-glob './*.m4a'
```

Групово, с нови изходни файлове:

```bash
albumtool.py -S itunes ech --sfa-glob './*.m4a' -o '{stem}.chaptered.m4a'
```

## Разделяне на Single-File албум на тракове

Командата `split-sfa` разделя single-file албум на отделни файлове според редактирания chapter файл.
Съкратено име: `split`.

Първо винаги dry-run:

```bash
albumtool.py split-sfa -F './Artist - 2024 - Album.mp3' -n
```

MP3 профил за Lexus:

```bash
albumtool.py split-sfa \
  -F './Artist - 2024 - Album.mp3' \
  -C cover.jpg \
  -P lexus-mp3
```

M4A/AAC профил за Lexus:

```bash
albumtool.py split-sfa \
  -F './Artist - 2024 - Album.mp3' \
  -C cover.jpg \
  -P lexus-m4a
```

По подразбиране:

- използва chapter файл `<audio-stem>.chapters.txt`;
- създава директория `<audio-stem>_tracks_<profile>`;
- кодира с 48 kHz sample rate;
- създава `playlist.m3u8`;
- вгражда metadata `title`, `artist`, `album`, `album_artist`, `track`;
- ако има обложка, подготвя я като Lexus-safe JPEG 500x500.

Bitrate:

- `--bitrate auto` е default;
- инструментът анализира входния аудио stream чрез `ffprobe`;
- избира най-близкия стандартен bitrate, който е `>=` текущия;
- стандартната скала е `96k, 112k, 128k, 144k, 160k, 192k, 224k, 256k, 320k`;
- можеш да зададеш явно `-b 144k`, `-b 160k` и т.н.

Пример:

```bash
albumtool.py split-sfa \
  -F './Holy_ground_music_smile_curve.mp3' \
  -a 'Geron Davis' \
  -A 'Holy Ground' \
  -C cover.jpeg \
  -P lexus-mp3 \
  -n
```

Реално изпълнение:

```bash
albumtool.py split-sfa \
  -F './Holy_ground_music_smile_curve.mp3' \
  -a 'Geron Davis' \
  -A 'Holy Ground' \
  -C cover.jpeg \
  -P lexus-mp3
```

Ако целевите файлове вече съществуват, командата спира. За презапис:

```bash
albumtool.py split-sfa -F './Album.mp3' --force
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

SFA с Lexus-safe JPEG обложка:

```bash
albumtool.py -S itunes ech -F './Ron Kenoly - 1993 - God Is Able.m4a' -T -C cover.jpg -P lexus-jpeg-500 --dry-run
albumtool.py -S itunes ech -F './Ron Kenoly - 1993 - God Is Able.m4a' -T -C cover.jpg -P lexus-jpeg-500
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
scan / sc            проверка, не променя файлове
rename / ren / rn    само преименува файлове
tag / tg             само записва metadata
run-all / all / ra   преименува и тагва multi-file албум
rename-dirs / dirs / rd
                     преименува album директории
cover / cov          изтегля локална обложка от metadata източника
chapters / ch        генерира chapters.txt за single-file албум
embed-chapters       вгражда chapters
embed / ech          съкратени имена за embed-chapters
split-sfa / split / sfs
                     разделя single-file албум на отделни тракове
```
