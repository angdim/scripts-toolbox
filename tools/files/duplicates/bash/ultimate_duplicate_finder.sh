#!/usr/bin/env bash
# scripts-toolbox: entrypoint

# ============================================
# Търсач на дублирани файлове за Ubuntu 24.04
# - Много пътища, филтри, изключения и минимален размер
# - Режим само между директории, прогрес и измерване на време
# - CSV + HTML (с размери и линкове)
# - Списък за изтриване (без триене)
# ============================================

human_size() {
  local bytes=$1

  if (( bytes < 1048576 )); then
    # под 1 MB → KB
    awk "BEGIN {printf \"%.2f KB\", $bytes/1024}"
  elif (( bytes < 1073741824 )); then
    # между 1 MB и 1 GB → MB
    awk "BEGIN {printf \"%.2f MB\", $bytes/1048576}"
  else
    # над 1 GB → MB + GB
    local mb
    local gb
    mb=$(awk "BEGIN {printf \"%.2f\", $bytes/1048576}")
    gb=$(awk "BEGIN {printf \"%.2f\", $bytes/1073741824}")
    echo "${mb} MB (${gb} GB)"
  fi
}

set -o pipefail

SCRIPT_START=$(date +%s)

clear
echo "=== Пълен търсач на дубликати (Ubuntu 24.04) ==="
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

if ((${#PATHS[@]} == 0)); then
  echo "Не са подадени валидни пътища. Прекратяване."
  exit 1
fi

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
read -rp "Минимален размер на файл в мегабайти (пример: 10). Остави празно за без ограничение:
> " min_size_mb

MIN_SIZE_BYTES=0
if [[ -n "$min_size_mb" ]]; then
  if [[ "$min_size_mb" =~ ^[0-9]+$ ]]; then
    MIN_SIZE_BYTES=$((min_size_mb * 1024 * 1024))
  else
    echo "Невалиден минимален размер, игнорирам (няма да има ограничение)."
    MIN_SIZE_BYTES=0
  fi
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
echo "Режим:"
echo "  1) Дубликати вътре и между всички пътища"
echo "  2) Само дубликати между различните пътища (игнорира вътрешните за един и същ път)"
read -rp "Избери 1 или 2 (по подразбиране 1): " mode_choice

MODE_BETWEEN_ONLY=0
if [[ "$mode_choice" == "2" ]]; then
  MODE_BETWEEN_ONLY=1
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
# SIMPLE PROGRESS HELPER
# -------------------------------
show_progress() {
  local current=$1
  local total=$2
  if (( total > 0 )); then
    local percent=$(( 100 * current / total ))
    echo -ne "Прогрес: $percent% ($current/$total) \r"
  fi
}

time_diff() {
  local start=$1
  local end=$2
  echo $(( end - start ))
}

# -------------------------------
# СТЪПКА 1: СЪБИРАНЕ НА ФАЙЛОВЕ
# -------------------------------
STEP1_START=$(date +%s)
echo "Събирам файлове..." | tee -a "$LOG"

ALL_FILES=()
ALL_FILES_SOURCE=()
ALL_FILES_SIZE=()

for P in "${PATHS[@]}"; do
  if [[ -d "$P" ]]; then
    CMD=(find "$P" -type f)

    # Изключвания (директории)
    for EX in "${EXCLUSIONS[@]}"; do
      CMD+=( -not -path "$EX/*" )
    done

    # Минимален размер
    if (( MIN_SIZE_BYTES > 0 )); then
      CMD+=( -size +"${MIN_SIZE_BYTES}c" )
    fi

    count_before=${#ALL_FILES[@]}
    while IFS= read -r -d '' F; do
      # Филтър по разширения
      if ((${#EXTENSIONS[@]} > 0)); then
        filename=$(basename "$F")
        ext="${filename##*.}"
        if [[ "$filename" == "$ext" ]]; then
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

      size=$(stat -c%s -- "$F" 2>/dev/null || echo "")
      [[ -z "$size" ]] && continue

      ALL_FILES+=("$F")
      ALL_FILES_SOURCE+=("$P")
      ALL_FILES_SIZE+=("$size")
    done < <("${CMD[@]}" -print0 2>/dev/null)

    count_after=${#ALL_FILES[@]}
    echo "Път '$P': добавени $((count_after - count_before)) файла." | tee -a "$LOG"
  else
    echo "Предупреждение: '$P' не е валидна директория, пропускам." | tee -a "$LOG"
  fi
done

TOTAL=${#ALL_FILES[@]}
echo "Общо намерени файлове: $TOTAL" | tee -a "$LOG"

STEP1_END=$(date +%s)
echo "Стъпка 1 (събиране на файлове) време: $(time_diff "$STEP1_START" "$STEP1_END") сек." | tee -a "$LOG"
echo

if (( TOTAL == 0 )); then
  echo "Няма файлове по зададените критерии. Прекратяване."
  exit 0
fi

# -------------------------------
# СТЪПКА 2: ГРУПИРАНЕ ПО РАЗМЕР
# -------------------------------
STEP2_START=$(date +%s)
echo "Групиране по размер..." | tee -a "$LOG"

declare -A SIZE_MAP  # size -> списък от индекси (по ред в ALL_FILES)

for idx in "${!ALL_FILES[@]}"; do
  size="${ALL_FILES_SIZE[$idx]}"
  SIZE_MAP["$size"]+="$idx"$'\n'
done

MATCHING_SIZE_GROUPS=()
for size in "${!SIZE_MAP[@]}"; do
  count=$(printf "%s" "${SIZE_MAP[$size]}" | sed '/^$/d' | wc -l)
  if (( count > 1 )); then
    MATCHING_SIZE_GROUPS+=("$size")
  fi
done

echo "Размери с повече от един файл: ${#MATCHING_SIZE_GROUPS[@]}" | tee -a "$LOG"

STEP2_END=$(date +%s)
echo "Стъпка 2 (групиране по размер) време: $(time_diff "$STEP2_START" "$STEP2_END") сек." | tee -a "$LOG"
echo

# -------------------------------
# СТЪПКА 3: ФУНКЦИЯ ЗА ХЕШИРАНЕ
# -------------------------------
hash_file() {
  local file="$1"
  sha256sum -- "$file" 2>/dev/null | awk '{print $1}'
}

# -------------------------------
# СТЪПКА 3: ХЕШИРАНЕ НА СЪВПАДАЩИ РАЗМЕРИ
# -------------------------------
STEP3_START=$(date +%s)
echo "Хеширане на файлове със съвпадащи размери..." | tee -a "$LOG"

declare -A HASH_MAP   # hash -> списък от индекси

total_groups=${#MATCHING_SIZE_GROUPS[@]}
current_group=0

for size in "${MATCHING_SIZE_GROUPS[@]}"; do
  ((current_group++))
  show_progress "$current_group" "$total_groups"

  while IFS= read -r idx; do
    [[ -z "$idx" ]] && continue
    F="${ALL_FILES[$idx]}"
    [[ ! -f "$F" ]] && continue
    h=$(hash_file "$F")
    [[ -z "$h" ]] && continue
    HASH_MAP["$h"]+="$idx"$'\n'
  done <<< "${SIZE_MAP[$size]}"
done

echo -ne "\nХеширане: завършено.\n" | tee -a "$LOG"

STEP3_END=$(date +%s)
echo "Стъпка 3 (хеширане) време: $(time_diff "$STEP3_START" "$STEP3_END") сек." | tee -a "$LOG"
echo

# -------------------------------
# СТЪПКА 4: ТЪРСЕНЕ НА ДУБЛИКАТИ + REPORTS
# -------------------------------
STEP4_START=$(date +%s)
echo "Откриване на дубликати и генериране на отчети..." | tee -a "$LOG"

echo "hash,size_bytes,size_human,location" > "$CSV"
echo "<html><body><h1>Отчет за дубликати</h1><table border='1'>" > "$HTML"
echo "<tr><th>#</th><th>Hash</th><th>Size</th><th>Location</th><th>Отвори файл</th><th>Nemo команда (първите 2)</th></tr>" >> "$HTML"
: > "$DELETE_LIST"

duplicate_group_count=0

for h in "${!HASH_MAP[@]}"; do
  mapfile -t idx_list <<< "$(printf "%s" "${HASH_MAP[$h]}" | sed '/^$/d')"
  if ((${#idx_list[@]} > 1)); then
    files=()
    sources=()
    sizes=()
    for idx in "${idx_list[@]}"; do
      files+=("${ALL_FILES[$idx]}")
      sources+=("${ALL_FILES_SOURCE[$idx]}")
      sizes+=("${ALL_FILES_SIZE[$idx]}")
    done

    # between-only режим: поне 2 различни източника
    if (( MODE_BETWEEN_ONLY == 1 )); then
      unique_sources=$(printf "%s\n" "${sources[@]}" | sort -u | wc -l)
      if (( unique_sources < 2 )); then
        continue
      fi
    fi

    ((duplicate_group_count++))

    # Подготвяме команда за Nemo за първите два файла (ако има поне 2)
    nemo_cmd=""
    if ((${#files[@]} >= 2)); then
      f1="${files[0]}"
      f2="${files[1]}"
      nemo_cmd="nemo --no-desktop --browser --select \"$f1\" & nemo --no-desktop --browser --select \"$f2\" &"
    fi

    # CSV + HTML редове
    for i in "${!files[@]}"; do
      f="${files[$i]}"
      sz="${sizes[$i]}"

      sz_human=$(human_size "$sz")
echo "$h,$sz,$sz_human,$f" >> "$CSV"
      echo "$f" >> "$DELETE_LIST"  # после можеш да прецениш ръчно; ако искаш, лесно ще променим да пази първия

      # HTML:
      # - file:// линк
      # - escape за HTML
      esc_path=$(printf '%s\n' "$f" | sed 's/&/&amp;/g;s/</\&lt;/g;s/>/\&gt;/g')
      url_enc=$(printf '%s\n' "$f" | sed 's/ /%20/g;s/#/%23/g;s/

\[/\%5B/g;s/\]

/\%5D/g')

      if [[ $i -eq 0 ]]; then
        # Показваме Nemo командата само веднъж за групата (в първия ред)
        echo "<tr><td>$duplicate_group_count</td><td>$h</td><td>$sz</td><td>$esc_path</td><td><a href=\"file://$url_enc\">Отвори</a></td><td><code>$nemo_cmd</code></td></tr>" >> "$HTML"
      else
        echo "<tr><td>$duplicate_group_count</td><td>$h</td><td>$sz</td><td>$esc_path</td><td><a href=\"file://$url_enc\">Отвори</a></td><td></td></tr>" >> "$HTML"
      fi
    done

    echo "" >> "$DELETE_LIST"
  fi
done

echo "</table></body></html>" >> "$HTML"

STEP4_END=$(date +%s)
echo "Стъпка 4 (дубликати + отчети) време: $(time_diff "$STEP4_START" "$STEP4_END") сек." | tee -a "$LOG"
echo "Намерени групи дубликати: $duplicate_group_count" | tee -a "$LOG"

# -------------------------------
# TOTAL TIME
# -------------------------------
SCRIPT_END=$(date +%s)
TOTAL_TIME=$(time_diff "$SCRIPT_START" "$SCRIPT_END")

echo
echo "=== Готово! ==="
echo "Общо време за изпълнение: ${TOTAL_TIME} сек."
echo "Отчетите са създадени в текущата директория:"
echo " - $CSV"
echo " - $HTML"
echo " - $LOG"
echo " - $DELETE_LIST (само списък, скриптът НЕ трие нищо)"
echo

echo "Общо време за изпълнение: ${TOTAL_TIME} сек." >> "$LOG"
