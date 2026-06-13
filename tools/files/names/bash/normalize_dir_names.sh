#!/usr/bin/env bash
# scripts-toolbox: entrypoint
# Предназначение: нормализира имената на директории според normalize.conf.

# Откриване на директорията на скрипта (работи и със symlink)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

# Конфигурационен файл: първо до скрипта, после стандартното място в repo структурата.
LOCAL_CONFIG="$SCRIPT_DIR/normalize.conf"
REPO_CONFIG="$SCRIPT_DIR/../../../config/normalize.conf"
CONFIG=""

# Зареждане на конфигурацията
if [ -f "$LOCAL_CONFIG" ]; then
    CONFIG="$LOCAL_CONFIG"
elif [ -f "$REPO_CONFIG" ]; then
    CONFIG="$REPO_CONFIG"
fi

valid_letters=""
valid_symbols=""
if [ -n "$CONFIG" ]; then
    # shellcheck source=/dev/null
    source "$CONFIG"
else
    echo "Грешка: липсва конфигурационен файл: $LOCAL_CONFIG или $REPO_CONFIG"
    exit 1
fi

if [ -z "$valid_letters" ] || [ -z "$valid_symbols" ]; then
    echo "Грешка: конфигурацията трябва да задава valid_letters и valid_symbols."
    exit 1
fi

DRYRUN=0
LOGFILE=""
TARGET_DIR=""

show_help() {
    cat <<EOF
Употреба: $0 [опции] /път/към/директории

Опции:
  -h, --help          Показва това ръководство
  --dry-run           Показва какво ще се промени, без да извършва промени
  --log FILE          Записва всички промени във файл
  (без опции)         Извършва реално преименуване

Описание:
  Скриптът нормализира имената на директории според правилата:
    - валидни букви: латиница + кирилица + цифри
    - валидни символи: . _ -
    - интервали около валидни символи се премахват
    - недопустими символи → "_"
    - последователни "_" → един "_"
    - водещи/крайни "_" НЕ се премахват
    - dry-run режим и логване са налични
    - статистика след изпълнение

Конфигурация:
  Настройките се зареждат от normalize.conf
EOF
}

# Статистика
total=0
changed=0
skipped=0

# Аргументи
while [[ "$1" != "" ]]; do
    case "$1" in
        -h|--help) show_help; exit 0 ;;
        --dry-run) DRYRUN=1 ;;
        --log) shift; LOGFILE="$1" ;;
        *) TARGET_DIR="$1" ;;
    esac
    shift
done

if [ -z "$TARGET_DIR" ]; then
    show_help
    exit 1
fi

log() { [ -n "$LOGFILE" ] && echo "$1" >> "$LOGFILE"; }

regex_escape_char_class() {
    printf '%s' "$1" | sed 's/[][\\.^$*]/\\&/g; s/-/\\-/g'
}

normalize_name() {
    local escaped_symbols
    escaped_symbols=$(regex_escape_char_class "$valid_symbols")
    printf '%s' "$1" \
    | sed -E "s/[[:space:]]*([$escaped_symbols])[[:space:]]*/\1/g" \
    | sed "s/[^[:alnum:]$escaped_symbols]/_/g" \
    | sed 's/_\+/_/g'
}

while IFS= read -r dir; do
    total=$((total + 1))

    base="$(basename "$dir")"
    parent="$(dirname "$dir")"
    new="$(normalize_name "$base")"

    if [ "$base" = "$new" ]; then
        skipped=$((skipped + 1))
        continue
    fi

    changed=$((changed + 1))
    echo "DIR: $dir → $parent/$new"
    log "DIR: $dir → $parent/$new"

    [ "$DRYRUN" -eq 0 ] && mv "$dir" "$parent/$new"
done < <(find "$TARGET_DIR" -depth -type d)

echo "=== Статистика ==="
echo "Общо: $total"
echo "Променени: $changed"
echo "Без промяна: $skipped"
