# Scripts Toolbox Catalog

Автоматично генериран каталог на скриптовете в колекцията.

## Как Да Ползваш Каталога

- `scripts-catalog list` показва всички активни entrypoint скриптове.
- `scripts-catalog search QUERY` търси по команда, описание, категория и път.
- `scripts-catalog show COMMAND` показва подробности за конкретен скрипт.
- `scripts-catalog help COMMAND` показва как да извикаш помощта на конкретен скрипт.
- `scripts-catalog removed` показва архивираните/изтрити скриптове.

## Активни Скриптове

### bootstrap

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| Install-ToPath | PowerShell | Windows | Инсталира scripts-toolbox командите в Windows чрез .cmd wrapper-и. | `Install-ToPath -Help` | `bootstrap/windows/Install-ToPath.ps1` |

### catalog

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| scripts-catalog | Python | Cross-platform/Python | Енциклопедичен каталог за scripts-toolbox. | `scripts-catalog --help` | `tools/catalog/python/scripts_catalog.py` |

### files/duplicates

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| DuplicateFinder-Win10 | PowerShell | Cross-platform PowerShell | Търси дублирани файлове в един или повече Windows пътища. | `DuplicateFinder-Win10 -Help` | `tools/files/duplicates/powershell/DuplicateFinder-Win10.ps1` |
| Find-Duplicates | PowerShell | Cross-platform PowerShell | Търси дублирани файлове в един или повече Windows пътища. | `Find-Duplicates -Help` | `tools/files/duplicates/powershell/Find-Duplicates.ps1` |
| Ultimate-Duplicate-Finder | PowerShell | Cross-platform PowerShell | Търси дублирани файлове в един или повече Windows пътища. | `Ultimate-Duplicate-Finder -Help` | `tools/files/duplicates/powershell/Ultimate-Duplicate-Finder.ps1` |
| Ultimate-DuplicateFinder-Win10 | PowerShell | Cross-platform PowerShell | Търси дублирани файлове в един или повече Windows пътища. | `Ultimate-DuplicateFinder-Win10 -Help` | `tools/files/duplicates/powershell/Ultimate-DuplicateFinder-Win10.ps1` |
| advanced_duplicate_finder | Bash | Linux/Unix | Няма извлечено описание. Стартирай help командата за повече информация. | `advanced_duplicate_finder --help` | `tools/files/duplicates/bash/advanced_duplicate_finder.sh` |
| deep_duplicate_scan | Bash | Linux/Unix | Няма извлечено описание. Стартирай help командата за повече информация. | `deep_duplicate_scan --help` | `tools/files/duplicates/bash/deep_duplicate_scan.sh` |
| find_duplicates | Bash | Linux/Unix | търси дублирани файлове в два зададени дяла/директории чрез SHA256 хешове. | `find_duplicates --help` | `tools/files/duplicates/bash/find_duplicates.sh` |
| ultimate_duplicate_finder | Bash | Linux/Unix | Няма извлечено описание. Стартирай help командата за повече информация. | `ultimate_duplicate_finder --help` | `tools/files/duplicates/bash/ultimate_duplicate_finder.sh` |
| ultimate_duplicate_finder_improved | Bash | Linux/Unix | Няма извлечено описание. Стартирай help командата за повече информация. | `ultimate_duplicate_finder_improved --help` | `tools/files/duplicates/bash/ultimate_duplicate_finder_improved.sh` |

### files/names

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| normalize_all_names | Bash | Linux/Unix | нормализира имената на файлове и директории според normalize.conf. | `normalize_all_names --help` | `tools/files/names/bash/normalize_all_names.sh` |
| normalize_dir_names | Bash | Linux/Unix | нормализира имената на директории според normalize.conf. | `normalize_dir_names --help` | `tools/files/names/bash/normalize_dir_names.sh` |
| normalize_file_names | Bash | Linux/Unix | нормализира имената на файлове според normalize.conf. | `normalize_file_names --help` | `tools/files/names/bash/normalize_file_names.sh` |

### media/audio

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| albumtool | Python | Cross-platform/Python | Инструмент за разпознаване, преименуване, тагване и chapter обработка на аудио албуми. | `albumtool --help` | `tools/media/audio/python/albumtool.py` |
| audio_peak_eq | Python | Cross-platform/Python | Инструмент за Linux за channel balance, peak-базирано усилване и EQ обработка чрез FFmpeg филтри. | `audio_peak_eq --help` | `tools/media/audio/python/audio_peak_eq.py` |
| convert_to_mp3 | Bash | Linux/Unix | Няма извлечено описание. Стартирай help командата за повече информация. | `convert_to_mp3 --help` | `tools/media/audio/bash/convert_to_mp3.sh` |
| generate_playlist | Bash | Linux/Unix | Няма извлечено описание. Стартирай help командата за повече информация. | `generate_playlist --help` | `tools/media/audio/bash/generate_playlist.sh` |
| m4a2mp3_converter | Python | Cross-platform/Python | M4A към MP3 конвертор с аудио обработка чрез FFmpeg. | `m4a2mp3_converter --help` | `tools/media/audio/python/m4a2mp3_converter.py` |
| split_by_silence | Python | Cross-platform/Python | Автоматично разделя audio/video файл на отделни тракове според паузи/тишина. | `split_by_silence --help` | `tools/media/audio/python/split_by_silence.py` |

### media/speech

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| song_recognize | Python | Cross-platform/Python | Автоматично разпознава аудио файлове чрез Shazam API и ги копира с разпознати имена. | `song_recognize --help` | `tools/media/speech/python/song_recognize.py` |
| split_by_speaker_bat | Batch/CMD | Windows | изрязва видео сегменти по говорители според transcript timestamp-и. | `split_by_speaker_bat /?` | `tools/media/speech/windows/split_by_speaker.bat` |
| split_recognize | Python | Cross-platform/Python | Автоматично разделя аудио/видео файл на отделни тракове базирано на паузи/тишина. | `split_recognize --help` | `tools/media/speech/python/split_recognize.py` |
| split_video_by_speaker | Python | Cross-platform/Python | Изрязва видео сегменти по говорители въз основа на transcript файл с timestamp-и. | `split_video_by_speaker --help` | `tools/media/speech/python/split_video_by_speaker.py` |
| split_video_by_speaker_sh | Bash | Linux/Unix | изрязва video сегменти по говорители според transcript timestamp-и. | `split_video_by_speaker_sh --help` | `tools/media/speech/bash/split_video_by_speaker.sh` |

### media/video

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| split_media_by_time | Python | Cross-platform/Python | Разделя audio/video файл на последователни части с фиксирана продължителност и малко припокриване. | `split_media_by_time --help` | `tools/media/video/python/split_media_by_time.py` |
| split_media_by_time_sh | Bash | Linux/Unix | разделя audio/video файл на части с фиксирана продължителност и overlap. | `split_media_by_time_sh --help` | `tools/media/video/bash/split_media_by_time.sh` |
| video4lexus | Python | Cross-platform/Python | Конвертира видео към формат и ограничения, подходящи за Lexus infotainment системи. | `video4lexus --help` | `tools/media/video/python/video4lexus.py` |
| video4lexus_sh | Bash | Linux/Unix | конвертира video файлове към ограничения, подходящи за Lexus infotainment системи. | `video4lexus_sh --help` | `tools/media/video/bash/video4lexus.sh` |
| video4lexus_v2 | Python | Cross-platform/Python | Втора версия на video4lexus конвертор с FFmpeg профил за Lexus infotainment системи. | `video4lexus_v2 --help` | `tools/media/video/python/video4lexus_v2.py` |
| video4lexus_v3 | Python | Cross-platform/Python | Трета версия на video4lexus конвертор с допълнителни проверки и автоматични корекции. | `video4lexus_v3 --help` | `tools/media/video/python/video4lexus_v3.py` |

### text/transcript

| Команда | Технология | Платформа | Описание | Помощ | Път |
|---|---|---|---|---|---|
| extract_speakers | Python | Cross-platform/Python | Извлича репликите на всеки говорител от transcript и създава отделен текстов файл за всеки. | `extract_speakers --help` | `tools/text/transcript/python/extract_speakers.py` |
| fix_paragraphs | Python | Cross-platform/Python | Нормализира transcript абзаци, като обединява редовете на всяка реплика в един чист параграф. | `fix_paragraphs --help` | `tools/text/transcript/python/fix_paragraphs.py` |
| process_transcript | Python | Cross-platform/Python | Обединява последователни transcript реплики на един и същ говорител в общи параграфи. | `process_transcript --help` | `tools/text/transcript/python/process_transcript.py` |
| process_transcript_time_offset | Python | Cross-platform/Python | Прилага времево отместване върху transcript timestamp-и и обединява последователни реплики. | `process_transcript_time_offset --help` | `tools/text/transcript/python/process_transcript_time_offset.py` |
| split_by_speaker | Python | Cross-platform/Python | Разделя transcript по говорители и може да генерира общ файл, отделни файлове, JSON и timestamp списъци. | `split_by_speaker --help` | `tools/text/transcript/python/split_by_speaker.py` |
| split_by_speaker_ps1 | PowerShell | Cross-platform PowerShell | Разделя transcript по говорители с обединяване на последователни блокове. | `split_by_speaker_ps1 -Help` | `tools/text/transcript/powershell/split_by_speaker.ps1` |

## Архив / Изтрити Скриптове

Няма регистрирани изтрити скриптове.
