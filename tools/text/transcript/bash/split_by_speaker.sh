#!/usr/bin/env bash
# scripts-toolbox: no-path
# !!! НЕ РАБОТИ !!! Ползвай ./python/split_by_speaker.py
# split_by_speaker.sh
#
# Описание:
#   Скриптът обработва транскрипт във формат:
#       [HH:MM:SS] Име на говорител: текст...
#
#   Основна функционалност:
#     • По подразбиране: създава ЕДИН общ файл (combined.txt),
#       в който всички последователни реплики на един и същ говорител
#       се обединяват в един абзац.
#
#     • Всеки абзац съдържа:
#           [първи timestamp] Име на говорител: текст текст текст...
#
#     • Между абзаците има ТОЧНО 1 празен ред.
#
#   Допълнителни опции:
#     --split            Създава отделни файлове за всеки говорител
#     --both             Общ файл + отделни файлове
#     --output-dir DIR   Директория за резултатите
#     --json             Генерира JSON метаданни
#     --normalize        Нормализира имена (SPK_01 → SPK_1)
#     --video            Генерира списъци за видео рязане (timestamps)
#     --log FILE         Записва лог файл
#
#   Скриптът разпознава ПРОИЗВОЛНИ имена на говорители:
#       - L.A. Marzulli
#       - Debora
#       - Person One
#       - Някой човек
#       - some_person
#
#   Логика на обединяване:
#     - Ако следващата реплика е от същия говорител → добавя се към текущия абзац.
#     - Ако е от нов говорител → текущият абзац се затваря и започва нов.
#
#   Гаранции:
#     - Няма сливане на абзаци.
#     - Няма липсващи имена.
#     - Няма липсващи timestamps.
#     - Няма двойни празни редове.
#     - Няма липсващи празни редове.
#

###############################################
# DEFAULTS
###############################################
OUTPUT_DIR="."
DO_SPLIT=0
DO_BOTH=0
JSON_OUTPUT=0
NORMALIZE=0
VIDEO_MODE=0
LOG_FILE=""
COMMON_FILE="combined.txt"

###############################################
# HELP
###############################################
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Употреба: $0 transcript.txt [опции]"
    echo
    echo "Опции:"
    echo "  --split            Създава отделни файлове за всеки говорител"
    echo "  --both             Общ файл + отделни файлове"
    echo "  --output-dir DIR   Директория за резултатите"
    echo "  --json             JSON метаданни"
    echo "  --normalize        Нормализация на имената"
    echo "  --video            FFmpeg списъци за рязане"
    echo "  --log FILE         Лог файл"
    exit 0
fi

###############################################
# INPUT FILE
###############################################
INPUT="$1"
shift

if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
    echo "Грешка: подай валиден входен файл."
    exit 1
fi

###############################################
# PARSE OPTIONS
###############################################
while [[ $# -gt 0 ]]; do
    case "$1" in
        --split) DO_SPLIT=1; shift ;;
        --both) DO_BOTH=1; shift ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --json) JSON_OUTPUT=1; shift ;;
        --normalize) NORMALIZE=1; shift ;;
        --video) VIDEO_MODE=1; shift ;;
        --log) LOG_FILE="$2"; shift 2 ;;
        *) echo "Непозната опция: $1"; exit 1 ;;
    esac
done

mkdir -p "$OUTPUT_DIR"

###############################################
# LOG FUNCTION
###############################################
log() { [[ -n "$LOG_FILE" ]] && echo "$1" >> "$LOG_FILE"; }

###############################################
# REGEX
###############################################
regex="^\[([0-9]{2}:[0-9]{2}:[0-9]{2})\][[:space:]]+([^:]+):[[:space:]]*(.*)$"

###############################################
# DATA STRUCTURES
###############################################
declare -A TEXTS
declare -A TIMES
declare -A COUNT

LAST_SPK=""
CURRENT_BLOCK=""

###############################################
# FLUSH BLOCK (затваряне на абзац)
###############################################
flush_block() {
    if [[ -n "$CURRENT_BLOCK" && -n "$LAST_SPK" ]]; then
        TEXTS[$LAST_SPK]="${TEXTS[$LAST_SPK]}${CURRENT_BLOCK}"$'\n'
        CURRENT_BLOCK=""
    fi
}

###############################################
# PROCESS FILE
###############################################
while IFS= read -r line; do
    if [[ $line =~ $regex ]]; then
        TIME="${BASH_REMATCH[1]}"
        SPK="${BASH_REMATCH[2]}"
        TEXT="${BASH_REMATCH[3]}"

        [[ $NORMALIZE -eq 1 ]] && SPK=$(echo "$SPK" | sed -E 's/_0+([0-9])/_\1/')

        if [[ "$SPK" != "$LAST_SPK" ]]; then
            flush_block
            CURRENT_BLOCK="[$TIME] $SPK: $TEXT"$'\n'
            TIMES[$SPK]="${TIMES[$SPK]} $TIME"
            COUNT[$SPK]=$((COUNT[$SPK]+1))
        else
            CURRENT_BLOCK="${CURRENT_BLOCK}${TEXT} "
        fi

        LAST_SPK="$SPK"
    fi
done < "$INPUT"

flush_block

###############################################
# COMMON FILE
###############################################
if [[ $DO_SPLIT -eq 0 || $DO_BOTH -eq 1 ]]; then
    OUT="$OUTPUT_DIR/$COMMON_FILE"
    : > "$OUT"
    for SPK in "${!TEXTS[@]}"; do
        echo "${TEXTS[$SPK]}" >> "$OUT"
        echo "" >> "$OUT"
    done
    log "Общ файл: $OUT"
fi

###############################################
# SPLIT FILES
###############################################
if [[ $DO_SPLIT -eq 1 || $DO_BOTH -eq 1 ]]; then
    for SPK in "${!TEXTS[@]}"; do
        SAFE=$(echo "$SPK" | tr ' ' '_' | tr -cd '[:alnum:]_')
        OUTFILE="$OUTPUT_DIR/${SAFE}.txt"
        echo "${TEXTS[$SPK]}" > "$OUTFILE"
        echo "" >> "$OUTFILE"

        if [[ $VIDEO_MODE -eq 1 ]]; then
            LIST="$OUTPUT_DIR/${SAFE}_video_list.txt"
            : > "$LIST"
            for T in ${TIMES[$SPK]}; do echo "$T" >> "$LIST"; done
        fi
    done
fi

###############################################
# JSON OUTPUT
###############################################
if [[ $JSON_OUTPUT -eq 1 ]]; then
    echo "{"
    FIRST=1
    for SPK in "${!TEXTS[@]}"; do
        [[ $FIRST -eq 0 ]] && echo ","
        FIRST=0
        SAFE=$(echo "$SPK" | tr ' ' '_' | tr -cd '[:alnum:]_')
        echo "  \"$SPK\": { \"file\": \"${SAFE}.txt\", \"count\": ${COUNT[$SPK]} }"
    done
    echo "}"
fi

echo "Готово."
