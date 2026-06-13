#!/usr/bin/env bash
# scripts-toolbox: entrypoint

# ============================================
# Търсач на дублирани файлове за Ubuntu 24.04
# Много пътища, филтри и изключения
# ============================================

set -o pipefail

clear
echo "=== Разширено търсене на дубликати (Ubuntu 24.04) ==="
echo

# -------------------------------
# ПОТРЕБИТЕЛСКИ ВХОД
# -------------------------------
read -rp "Въведи пътищата (дялове/директории), разделени със запетая:
Пример: /mnt/external/disk1, /mnt/external/disk2
> " input_paths

IFS=',' read -r -a PATHS_RAW <<< "$input_paths"
PATHS=()
for p in "${PATHS_RAW[@]}"; do
  p_trimmed=$(echo "$p" | sed 's/^ *//;s/ *$//')
  [[ -n "$p_trimmed" ]] && PATHS+=("$p_trimmed")
done

echo
read -rp "Филтър по разширения (пример: jpg,mp4,pdf). Остави празно за всички:
> " ext_input

EXTENSIONS=()
if [[ -n "$ext_input" ]]; then
  IFS=',' read -r -a EXT_RAW <<< "$ext_input"
  for e in "${EXT_RAW[@]}"; do
    e_trimmed=$(echo "$e" | sed 's/^ *//;s/ *$//')
    [[ -n "$e_trimmed" ]] && EXTENSIONS+=("$(echo "$e_trimmed" | tr '[:upper:]' '[:lower:]')")
  done
fi

echo
read -rp "Изключване на папки (пример: /mnt/external/disk1/Temp, /mnt/external/disk2/Trash).
Остави празно за никакви изключения:
> " excl_input

EXCLUSIONS=()
if [[ -n "$excl_input" ]]; then
  IFS=',' read -r -a EXCL_RAW <<< "$excl_input"
  for ex in "${EXCL_RAW[@]}"; do
    ex_trimmed=$(echo "$ex" | sed 's/^ *//;s/ *$//')
    [[ -n "$ex_trimmed" ]] && EXCLUSIONS+=("$ex_trimmed")
  done
fi

echo
echo "=== Стартиране на сканирането... ==="
echo

# -------------------------------
# ИЗХОДНИ ФАЙЛОВЕ
# -------------------------------
LOG="scan.log"
CSV="duplicates_report.csv"
HTML="duplicates_report.html"
DELETE_LIST="duplicates_to_delete.txt"

echo "=== Сканирането за дубликати започна ===" > "$LOG"
date >> "$LOG"

# -------------------------------
# СЪБИРАНЕ НА ФАЙЛОВЕ
# -------------------------------
echo "Събирам файлове..." | tee -a "$LOG"

ALL_FILES=()

for P in "${PATHS[@]}"; do
  if [[ -d "$P" ]]; then
    # Базов find
    CMD=(find "$P" -type f)

    # Изключвания (директории)
    for EX in "${EXCLUSIONS[@]}"; do
      CMD+=( -not -path "$EX/*" )
    done

    # Изпълнение
    while IFS= read -r -d '' F; do
      # Филтър по разширения
      if ((${#EXTENSIONS[@]} > 0)); then
        filename=$(basename "$F")
        ext="${filename##*.}"
        if [[ "$filename" == "$ext" ]]; then
          # няма разширение
          continue
        fi
        ext_lc=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
        match=0
        for e in "${EXTENSIONS[@]}"; do
          if [[ "$ext_lc" == "$e" ]]; then
            match=1
            break
          fi
        done
        (( match == 0 )) && continue
      fi

      ALL_FILES+=("$F")
    done < <("${CMD[@]}" -print0 2>/dev/null)
  else
    echo "Предупреждение: '$P' не е валидна директория, пропускам." | tee -a "$LOG"
  fi
done

TOTAL=${#ALL_FILES[@]}
echo "Намерени файлове: $TOTAL" | tee -a "$LOG"

if (( TOTAL == 0 )); then
  echo "Няма файлове по зададените критерии. Прекратяване."
  exit 0
fi

# -------------------------------
# GROUP BY SIZE
# -------------------------------
echo "Групиране по размер..." | tee -a "$LOG"

declare -A SIZE_MAP

for F in "${ALL_FILES[@]}"; do
  if [[ -f "$F" ]]; then
    size=$(stat -c%s -- "$F" 2>/dev/null || echo "")
    [[ -z "$size" ]] && continue
    SIZE_MAP["$size"]+="$F"$'\n'
  fi
done

# Подготовка на групи с повече от 1 файл
MATCHING_SIZE_GROUPS=()
for size in "${!SIZE_MAP[@]}"; do
  # преброяване на редовете
  count=$(printf "%s" "${SIZE_MAP[$size]}" | sed '/^$/d' | wc -l)
  if (( count > 1 )); then
    MATCHING_SIZE_GROUPS+=("$size")
  fi
done

echo "Размери с повече от един файл: ${#MATCHING_SIZE_GROUPS[@]}" | tee -a "$LOG"

# -------------------------------
# HASH FUNCTION
# -------------------------------
hash_file() {
  local file="$1"
  sha256sum -- "$file" 2>/dev/null | awk '{print $1}'
}

# -------------------------------
# HASH MATCHING SIZES
# -------------------------------
echo "Хеширане на файлове със съвпадащи размери..." | tee -a "$LOG"

declare -A HASH_MAP

for size in "${MATCHING_SIZE_GROUPS[@]}"; do
  while IFS= read -r F; do
    [[ -z "$F" ]] && continue
    [[ ! -f "$F" ]] && continue
    h=$(hash_file "$F")
    [[ -z "$h" ]] && continue
    HASH_MAP["$h"]+="$F"$'\n'
  done <<< "${SIZE_MAP[$size]}"
done

# -------------------------------
# FIND DUPLICATES
# -------------------------------
echo "Откриване на дубликати..." | tee -a "$LOG"

# Инициализиране на файловете
echo "hash,location" > "$CSV"
echo "<html><body><h1>Отчет за дубликати</h1><table border='1'>" > "$HTML"
echo "<tr><th>Hash</th><th>Location</th></tr>" >> "$HTML"
: > "$DELETE_LIST"

duplicate_count=0

for h in "${!HASH_MAP[@]}"; do
  # списък от файлове за този хеш
  mapfile -t files <<< "$(printf "%s" "${HASH_MAP[$h]}" | sed '/^$/d')"
  if (( ${#files[@]} > 1 )); then
    ((duplicate_count++))
    # CSV & HTML
    for f in "${files[@]}"; do
      echo "$h,$f" >> "$CSV"
      esc_path=$(printf '%s\n' "$f" | sed 's/&/&amp;/g;s/</\&lt;/g;s/>/\&gt;/g')
      echo "<tr><td>$h</td><td>$esc_path</td></tr>" >> "$HTML"
    done

    # DELETE LIST – пазим първия, останалите са кандидати за изтриване
    for ((i=1; i<${#files[@]}; i++)); do
      echo "${files[$i]}" >> "$DELETE_LIST"
    done
  fi
done

echo "</table></body></html>" >> "$HTML"

echo "Намерени групи дубликати: $duplicate_count" | tee -a "$LOG"

echo
echo "=== Готово! ==="
echo "Отчетите са създадени в текущата директория:"
echo " - $CSV"
echo " - $HTML"
echo " - $LOG"
echo " - $DELETE_LIST (само списък, скриптът НЕ трие нищо)"
echo
