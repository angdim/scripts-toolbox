#!/usr/bin/env bash
# scripts-toolbox: entrypoint
#
# convert_to_mp3.sh
#
# Скрипт за:
# - рекурсивно намиране на всички не-MP3 аудио/видео файлове в подадена директория
# - конвертиране към MP3 чрез ffmpeg с профили от mp3_profiles.ini
# - отделна политика за триене на оригинални аудио и видео файлове
# - dry-run режим (без реални промени)
# - паралелна обработка (-j)
# - лог файл с успешни и неуспешни операции
# - статистика по разширения и общо/средно време
#
# Популярни ffmpeg настройки за MP3 (примерни профили, описани и в mp3_profiles.ini):
# - Музика (високо качество):
#   -codec:a libmp3lame -b:a 320k -ar 44100 -ac 2
# - Музика (добро качество, по-малък размер):
#   -codec:a libmp3lame -b:a 192k -ar 44100 -ac 2
# - Говор / подкаст:
#   -codec:a libmp3lame -b:a 96k -ar 22050 -ac 1
# - Моно, нисък битрейт:
#   -codec:a libmp3lame -b:a 64k -ac 1
# - „Прозрачно“ качество (VBR):
#   -codec:a libmp3lame -qscale:a 0

# Принудително изпълнение с Bash, дори ако е стартиран през sh
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

# Път до реалния файл, дори ако е symlink
REAL_PATH="$(readlink -f "$(command -v "$0")")"
SCRIPT_DIR="$(dirname "$REAL_PATH")"

# Конфигурационният файл винаги се намира до реалния скрипт
INI_FILE="$SCRIPT_DIR/mp3_profiles.ini"

SCRIPT_NAME="$(basename "$0")"
LOG_FILE="convert_to_mp3.log"

# Вътрешни списъци с поддържани разширения
AUDIO_EXT=("wav" "flac" "ogg" "aac" "m4a" "wma" "opus" "aiff" "aif" "alac")
VIDEO_EXT=("mp4" "mkv" "webm" "mov" "avi" "flv" "wmv" "mpeg" "mpg")

# Настройки по подразбиране
PROFILE_NAME="music"
DELETE_ORIGINAL_AUDIO="no"
DELETE_ORIGINAL_VIDEO="no"
DRY_RUN="no"
JOBS=1
ROOT_DIR=""

FFMPEG_PARAMS=""   # ще се попълни от профила

SUCCESS_COUNT=0
FAIL_COUNT=0
declare -A TIME_BY_FILE

format_time_hms() {
    local total="$1"
    local h=$(( total / 3600 ))
    local m=$(( (total % 3600) / 60 ))
    local s=$(( total % 60 ))
    printf "%02d:%02d:%02d" "$h" "$m" "$s"
}

print_help() {
    cat <<EOF
${SCRIPT_NAME} - рекурсивно конвертиране на аудио/видео файлове към MP3

Употреба:
  ${SCRIPT_NAME} [опции] ROOT_DIR

Опции:
  -h, --help
      Показва това помощно съобщение.

  -p, --profile NAME
      Име на профил от mp3_profiles.ini (напр. music, speech, mono_low).
      По подразбиране: music

  -n, --dry-run
      Dry-run режим: не конвертира и не трие нищо, само показва и логва
      какво БИ направил.

  -j, --jobs N
      Брой паралелни задачи (файлове), които да се обработват едновременно.
      По подразбиране: 1 (последователно).

  -da, --delete-original-audio y|n
      Дали да се трият оригиналните АУДИО файлове след успешна конверсия.

  -dv, --delete-original-video y|n
      Дали да се трият оригиналните ВИДЕО файлове след успешна конверсия.

Файлове:
  mp3_profiles.ini  (в директорията на скрипта)
  ${LOG_FILE}       (лог файл в текущата директория)

EOF
}

ext_in_list() {
    local ext="$1"; shift
    local e
    for e in "$@"; do
        if [[ "$ext" == "$e" ]]; then
            return 0
        fi
    done
    return 1
}

load_ini() {
    local ini="$1"
    [[ -f "$ini" ]] || return 0

    local section=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        # trim
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"

        # празен ред или коментар
        [[ -z "$line" || "${line:0:1}" == "#" || "${line:0:1}" == ";" ]] && continue

        # секция [name]
        if [[ "$line" =~ ^\[([^\]]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            continue
        fi


        # ключ=стойност
        if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"

            # trim key/value
            key="${key#"${key%%[![:space:]]*}"}"
            key="${key%"${key##*[![:space:]]}"}"
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"

            # махаме кавички
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"

            if [[ -n "$section" ]]; then
                local varname="${section}_${key}"
                printf -v "$varname" '%s' "$value"
            fi
        fi
    done < "$ini"
}


apply_ini_defaults() {
    load_ini "$INI_FILE"

    if [[ -n "${defaults_delete_original_audio-}" ]]; then
        DELETE_ORIGINAL_AUDIO="$defaults_delete_original_audio"
    fi
    if [[ -n "${defaults_delete_original_video-}" ]]; then
        DELETE_ORIGINAL_VIDEO="$defaults_delete_original_video"
    fi
}

get_profile_params() {
    local profile="$1"
    local varname="${profile}_params"
    if [[ -n "${!varname-}" ]]; then
        echo "${!varname}"
    else
        echo ""
    fi
}

log_msg() {
    local msg="$1"
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] $msg" | tee -a "$LOG_FILE" >&2
}

check_free_space() {
    local file="$1"
    local dir
    dir="$(dirname "$file")"
    local size_bytes
    size_bytes=$(stat -c%s "$file")
    local needed=$(( size_bytes * 2 ))
    local avail
    avail=$(df -P -B1 "$dir" | awk 'NR==2 {print $4}')
    (( avail >= needed ))
}

is_video_file() {
    local file="$1"
    if ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of csv=p=0 "$file" 2>/dev/null | grep -q "video"; then
        return 0
    else
        return 1
    fi
}

process_one_file() {
    local start_ts
    start_ts=$(date +%s%3N)   # милисекунди
    local file="$1"
    local profile="$PROFILE_NAME"
    local ffmpeg_params="$FFMPEG_PARAMS"
    local delete_audio="$DELETE_ORIGINAL_AUDIO"
    local delete_video="$DELETE_ORIGINAL_VIDEO"
    local dry_run="$DRY_RUN"

    local ext="${file##*.}"
    ext="${ext,,}"

    local is_video="no"
    if ext_in_list "$ext" "${VIDEO_EXT[@]}"; then
        is_video="yes"
    elif ext_in_list "$ext" "${AUDIO_EXT[@]}"; then
        is_video="no"
    else
        if is_video_file "$file"; then
            is_video="yes"
        else
            is_video="no"
        fi
    fi

    local out="${file%.*}.mp3"

    if [[ -f "$out" ]]; then
        log_msg "SKIP (output exists): $file -> $out"
        return 0
    fi

    if ! check_free_space "$file"; then
        log_msg "FAILED (no space): $file (недостатъчно свободно място)"

        return 1
    fi

    local cmd=(ffmpeg -y -hide_banner -loglevel error -i "$file")

    if [[ "$is_video" == "yes" ]]; then
        cmd+=(-vn)
    fi

    if [[ -n "$ffmpeg_params" ]]; then
        # shellcheck disable=SC2206
        extra=( $ffmpeg_params )
        cmd+=("${extra[@]}")
    fi

    cmd+=("$out")

    if [[ "$dry_run" == "yes" ]]; then
        log_msg "DRY-RUN: ${cmd[*]}"
        return 0
    fi

    local stderr
    if ! stderr="$("${cmd[@]}" 2>&1)"; then
        log_msg "FAILED: $file -> $out (profile: $profile, video: $is_video) ffmpeg error: $stderr"
        local end_ts
        end_ts=$(date +%s%3N)
        local duration=$((end_ts - start_ts))
        TIME_BY_FILE["$file"]=$duration
        ((FAIL_COUNT++))
        return 1
    fi

    log_msg "OK: $file -> $out (profile: $profile, video: $is_video)"
    local end_ts
    end_ts=$(date +%s%3N)
    local duration=$((end_ts - start_ts))
    TIME_BY_FILE["$file"]=$duration
    ((SUCCESS_COUNT++))


    if [[ "$is_video" == "yes" ]]; then
        if [[ "$delete_video" == "yes" ]]; then
            rm -f -- "$file" || log_msg "WARN: неуспешно изтриване на видео файл: $file"
        fi
    else
        if [[ "$delete_audio" == "yes" ]]; then
            rm -f -- "$file" || log_msg "WARN: неуспешно изтриване на аудио файл: $file"
        fi
    fi
}

parse_args() {
    local opt
    while [[ $# -gt 0 ]]; do
        opt="$1"
        case "$opt" in
            -h|--help)
                print_help
                exit 0
                ;;
            -p|--profile)
                PROFILE_NAME="$2"
                shift 2
                ;;
            -n|--dry-run)
                DRY_RUN="yes"
                shift
                ;;
            -j|--jobs)
                JOBS="$2"
                shift 2
                ;;
            -da|--delete-original-audio)
                case "$2" in
                    y|Y|yes|YES) DELETE_ORIGINAL_AUDIO="yes" ;;
                    n|N|no|NO)   DELETE_ORIGINAL_AUDIO="no" ;;
                    *) echo "Невалидна стойност за -da/--delete-original-audio: $2" >&2; exit 1 ;;
                esac
                shift 2
                ;;
            -dv|--delete-original-video)
                case "$2" in
                    y|Y|yes|YES) DELETE_ORIGINAL_VIDEO="yes" ;;
                    n|N|no|NO)   DELETE_ORIGINAL_VIDEO="no" ;;
                    *) echo "Невалидна стойност за -dv/--delete-original-video: $2" >&2; exit 1 ;;
                esac
                shift 2
                ;;
            --)
                shift
                break
                ;;
            -*)
                echo "Непозната опция: $opt" >&2
                exit 1
                ;;
            *)
                ROOT_DIR="$opt"
                shift
                ;;
        esac
    done

    if [[ -z "${ROOT_DIR:-}" ]]; then
        echo "Грешка: не е подадена ROOT_DIR директория." >&2
        echo "Използвай -h за помощ." >&2
        exit 1
    fi
}

main() {
    : > "$LOG_FILE"
    START_TIME=$(date +%s)

    apply_ini_defaults
    parse_args "$@"

    if [[ ! -d "$ROOT_DIR" ]]; then
        echo "Грешка: ROOT_DIR не е директория: $ROOT_DIR" >&2
        exit 1
    fi

    FFMPEG_PARAMS="$(get_profile_params "$PROFILE_NAME")"
    # Debug profile name - remove if successful
    echo "DEBUG: PROFILE_NAME=$PROFILE_NAME, FFMPEG_PARAMS='$FFMPEG_PARAMS'" >&2
    if [[ -z "$FFMPEG_PARAMS" ]]; then
        log_msg "WARN: няма дефинирани params за профил '$PROFILE_NAME' в $INI_FILE. Ще се използват ffmpeg по подразбиране."
    fi

    log_msg "Старт: ROOT_DIR=$ROOT_DIR, profile=$PROFILE_NAME, dry_run=$DRY_RUN, jobs=$JOBS, delete_audio=$DELETE_ORIGINAL_AUDIO, delete_video=$DELETE_ORIGINAL_VIDEO"

    # Събираме само аудио/видео файлове (без mp3)
    mapfile -t files < <(
        find "$ROOT_DIR" -type f ! -iname '*.mp3' | while read -r f; do
            ext="${f##*.}"
            ext="${ext,,}"
            if ext_in_list "$ext" "${AUDIO_EXT[@]}" || ext_in_list "$ext" "${VIDEO_EXT[@]}"; then
                echo "$f"
            fi
        done
    )

    if [[ "${#files[@]}" -eq 0 ]]; then
        log_msg "Няма файлове за обработка."
        END_TIME=$(date +%s)
        TOTAL_TIME=$((END_TIME - START_TIME))
        echo "----------------------------------------"
        echo "Статистика:"
        echo "Общо файлове за обработка: 0"
        echo "Общо време: $(format_time_hms "$TOTAL_TIME")"
        echo "----------------------------------------"
        exit 0
    fi

    # Паралелна обработка без xargs, с job control
    if (( JOBS <= 1 )); then
        for f in "${files[@]}"; do
            process_one_file "$f"
        done
    else
        running=0
        for f in "${files[@]}"; do
            process_one_file "$f" &
            ((running++))
            if (( running >= JOBS )); then
                wait -n
                ((running--))
            fi
        done
        wait
    fi

    END_TIME=$(date +%s)
    TOTAL_TIME=$((END_TIME - START_TIME))

    echo "----------------------------------------"
    echo "Статистика:"
    echo "Общо файлове за обработка: ${#files[@]}"
    echo "Успешни: $SUCCESS_COUNT"
    echo "Неуспешни: $FAIL_COUNT"

    # Статистика по разширения
    declare -A COUNT_BY_EXT
    for f in "${files[@]}"; do
        ext="${f##*.}"
        ext="${ext,,}"
        ((COUNT_BY_EXT["$ext"]++))
    done

    echo "Разширения:"
    for ext in "${!COUNT_BY_EXT[@]}"; do
        echo "  $ext : ${COUNT_BY_EXT[$ext]}"
    done

    # Минимално, максимално и средно време
    MIN_TIME=999999999
    MAX_TIME=0
    SUM_TIME=0

    for f in "${!TIME_BY_FILE[@]}"; do
        t=${TIME_BY_FILE[$f]}
        ((t < MIN_TIME)) && MIN_TIME=$t
        ((t > MAX_TIME)) && MAX_TIME=$t
        ((SUM_TIME += t))
    done

    if (( SUCCESS_COUNT > 0 )); then
        AVG_MS=$(( SUM_TIME / SUCCESS_COUNT ))
    else
        AVG_MS=0
    fi

    # Форматиране
    MIN_SEC_INT=$(( MIN_TIME / 1000 ))
    MIN_SEC_FRAC=$(( MIN_TIME % 1000 ))

    MAX_SEC_INT=$(( MAX_TIME / 1000 ))
    MAX_SEC_FRAC=$(( MAX_TIME % 1000 ))

    AVG_SEC_INT=$(( AVG_MS / 1000 ))
    AVG_SEC_FRAC=$(( AVG_MS % 1000 ))

    echo "Минимално време на файл: ${MIN_SEC_INT}.${MIN_SEC_FRAC} сек"
    echo "Максимално време на файл: ${MAX_SEC_INT}.${MAX_SEC_FRAC} сек"
    echo "Средно време на файл: ${AVG_SEC_INT}.${AVG_SEC_FRAC} сек"

    # Общо време
    echo "Общо време: $(format_time_hms "$TOTAL_TIME")"

    # Скорост
    if (( TOTAL_TIME > 0 )); then
        SPEED=$(echo "$SUCCESS_COUNT * 1000 / (TOTAL_TIME * 1000)" | bc 2>/dev/null || echo 0)
        echo "Скорост: $(printf "%.2f" "$SPEED") файла/сек"
    fi

    echo "----------------------------------------"

    log_msg "Край."
}

main "$@"
