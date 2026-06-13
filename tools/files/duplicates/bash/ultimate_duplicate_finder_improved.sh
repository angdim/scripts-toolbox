#!/usr/bin/env bash
# scripts-toolbox: entrypoint

# ============================================
# Търсач на дублирани файлове за Ubuntu 24.04
# ============================================

##### БЛОК 1 #####

set -o pipefail

SCRIPT_START=$(date +%s)

# Timestamp във формат YYYY-MM-DD-HH-MM-SS
TS=$(date +"%Y-%m-%d-%H-%M-%S")

# Имена на отчетните файлове (с timestamp в началото)
LOG="${TS}_scan.log"
CSV="${TS}_duplicates_report.csv"
HTML_LIGHT="${TS}_duplicates_report_light.html"
HTML_DARK="${TS}_duplicates_report_dark.html"
DELETE_LIST="${TS}_duplicates_to_delete.txt"
DELETE_SCRIPT="${TS}_delete_duplicates.sh"
HASH_CACHE_FILE=".duplicate_finder_hash_cache"

clear
# Цветове за терминала
RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
MAGENTA="\e[35m"
CYAN="\e[36m"
BOLD="\e[1m"
RESET="\e[0m"

info()    { echo -e "${CYAN}${1}${RESET}"; }
success() { echo -e "${GREEN}${1}${RESET}"; }
warn()    { echo -e "${YELLOW}${1}${RESET}"; }
error()   { echo -e "${RED}${1}${RESET}"; }
title()   { echo -e "${BOLD}${MAGENTA}${1}${RESET}"; }
step()    { echo -e "${BOLD}${BLUE}${1}${RESET}"; }

title "=== Пълен търсач на дубликати (Ubuntu 24.04) ==="
echo

##### БЛОК 2 #####

# Показване на прогрес
show_progress() {
  local current=$1
  local total=$2
  if (( total > 0 )); then
    local percent=$(( 100 * current / total ))
    echo -ne "${YELLOW}Прогрес:${RESET} ${GREEN}${percent}%${RESET} (${current}/${total}) \r"

  fi
}

# Разлика във време (секунди)
time_diff() {
  local start=$1
  local end=$2
  echo $(( end - start ))
}

# Форматиране на време: h:mm:ss (общо секунди)
format_duration() {
  local seconds=$1
  local h=$((seconds / 3600))
  local m=$(((seconds % 3600) / 60))
  local s=$((seconds % 60))
  printf "%d:%02d:%02d (%d секунди)" "$h" "$m" "$s" "$seconds"
}

# Човешки четим размер
# <1 MB → KB, 1MB–1GB → MB, >1GB → MB (GB)
human_size() {
  local bytes=$1

  if (( bytes < 1048576 )); then
    awk "BEGIN {printf \"%.2f KB\", $bytes/1024}"
  elif (( bytes < 1073741824 )); then
    awk "BEGIN {printf \"%.2f MB\", $bytes/1048576}"
  else
    local mb
    local gb
    mb=$(awk "BEGIN {printf \"%.2f\", $bytes/1048576}")
    gb=$(awk "BEGIN {printf \"%.2f\", $bytes/1073741824}")
    echo "${mb} MB (${gb} GB)"
  fi
}

# HTML escape за текст
html_escape() {
  sed 's/&/&amp;/g;s/</\&lt;/g;s/>/\&gt;/g'
}

# URL encode за file:// линкове (частично – достатъчно за пътища)
url_encode_path() {
  local p="$1"
  local out=""
  local i ch
  local len=${#p}
  for ((i=0; i<len; i++)); do
    ch="${p:$i:1}"
    case "$ch" in
      " ") out+='%20' ;;
      "#") out+='%23' ;;
      "[") out+='%5B' ;;
      "]") out+='%5D' ;;
      "(") out+='%28' ;;
      ")") out+='%29' ;;
      "'") out+='%27' ;;
      '"') out+='%22' ;;
      *) out+="$ch" ;;
    esac
  done
  printf '%s' "$out"
}

# Хеш функция с кеширане по (path|size|mtime)
hash_file() {
  local file="$1"

  # ако файлът не съществува – връщаме празно
  [[ ! -f "$file" ]] && return 1

  local size mtime key cached hash
  size=$(stat -c%s -- "$file" 2>/dev/null) || return 1
  mtime=$(stat -c%Y -- "$file" 2>/dev/null) || return 1
  key="$file|$size|$mtime"

  # Проверка в кеша
  if [[ -f "$HASH_CACHE_FILE" ]]; then
    cached=$(grep -F -- "$key" "$HASH_CACHE_FILE" 2>/dev/null | head -n1)
    if [[ -n "$cached" ]]; then
      # формат: path|size|mtime|hash
      hash="${cached##*|}"
      printf '%s\n' "$hash"
      return 0
    fi
  fi

  # Ако няма в кеша – изчисляваме
  hash=$(sha256sum -- "$file" 2>/dev/null | awk '{print $1}')
  [[ -z "$hash" ]] && return 1

  # Добавяме в кеша
  printf '%s|%s\n' "$key" "$hash" >> "$HASH_CACHE_FILE"

  printf '%s\n' "$hash"
  return 0
}

##### БЛОК 3 #####

# Започване на лог файла
{
  step "=== Сканирането за дубликати започна ==="
  date
  info "Отчетните файлове ще са:"
  info "LOG:          $LOG"
  info "CSV:          $CSV"
  info "HTML (light): $HTML_LIGHT"
  info "HTML (dark):  $HTML_DARK"
  info "DELETE LIST:  $DELETE_LIST"
  echo
} > "$LOG"

##### БЛОК 4 #####

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
  error "Не са подадени валидни пътища. Прекратяване."
  exit 1
fi

echo
info "Примери за филтри:"
info "  mp3"
info "  mp3,wav,flac"
info "  PMR*.mp3"
info "  */PMR*/09-*.mp3"
info "  !*/Temp/*"
info "  /PMR.*\\.mp3$/regex"
info "  audio"
info "  video"
info "  image/jpeg"
info "  size>10MB"
info "  date>2020-01-01"
info "  dir:/mnt/external/disk1/PMR"
info "  name_len>20"
echo

read -rp "Филтър по разширения/патърни (остави празно за всички): " ext_input

EXTENSIONS=()
PATTERNS_POSITIVE=()
PATTERNS_NEGATIVE=()
MIME_TYPES=()
CATEGORIES=()
REGEX_PATTERNS=()
DATE_FILTERS=()
SIZE_FILTERS=()
DIR_FILTERS=()
NAME_LEN_FILTERS=()

if [[ -n "$ext_input" ]]; then
  IFS=',' read -r -a FILTER_RAW <<< "$ext_input"

  for f in "${FILTER_RAW[@]}"; do
    f_trim=$(echo "$f" | tr -d '[:space:]')
  
    # 1) Отрицателни pattern-и
    if [[ "$f_trim" == "!"* ]]; then
        PATTERNS_NEGATIVE+=("${f_trim:1}")
        continue
    fi
  
    # 2) Regex филтри – маркер /regex в края
    if [[ "$f_trim" == */regex ]]; then
        REGEX_PATTERNS+=("${f_trim%/regex}")
        continue
    fi
  
    # 3) MIME типове – вида type/subtype, без * ? : и без начален /
    if [[ "$f_trim" == *"/"* && "$f_trim" != *"*"* && "$f_trim" != *"?"* && "$f_trim" != ":"* && "$f_trim" != /* ]]; then
        MIME_TYPES+=("$f_trim")
        continue
    fi
  
    # 4) Категории
    case "$f_trim" in
        audio|video|images|documents)
            CATEGORIES+=("$f_trim")
            continue
            ;;
    esac
  
    # 5) Филтър по дата: date>..., date<..., date>=..., date<=...
    if [[ "$f_trim" == date\>* || "$f_trim" == date\<* ]]; then
        DATE_FILTERS+=("$f_trim")
        continue
    fi
  
    # 6) Филтър по размер: size>10MB, size<500K и т.н.
    if [[ "$f_trim" == size\>* || "$f_trim" == size\<* ]]; then
        SIZE_FILTERS+=("$f_trim")
        continue
    fi
  
    # 7) Филтър по директория: dir:/път/...
    if [[ "$f_trim" == dir:* ]]; then
        DIR_FILTERS+=("${f_trim#dir:}")
        continue
    fi
  
    # 8) Филтър по дължина на име: name_len>20, name_len<100
    if [[ "$f_trim" == name_len\>* || "$f_trim" == name_len\<* ]]; then
        NAME_LEN_FILTERS+=("$f_trim")
        continue
    fi
  
    # 9) Pattern-и (ако съдържа * ? или /)
    if [[ "$f_trim" == *"*"* || "$f_trim" == *"?"* || "$f_trim" == *"/"* ]]; then
        PATTERNS_POSITIVE+=("$f_trim")
        continue
    fi
  
    # 10) Разширения
    f_trim="${f_trim#.}"
    f_trim="${f_trim#\*}"
    f_trim=$(echo "$f_trim" | tr '[:upper:]' '[:lower:]')
    [[ -n "$f_trim" ]] && EXTENSIONS+=("$f_trim")
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
    warn "Невалиден минимален размер, игнорирам (няма да има ограничение)."
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
info "Режим:"
info "  1) Дубликати вътре и между всички пътища"
info "  2) Само дубликати между различните пътища (игнорира вътрешните за един и същ път)"
read -rp "Избери 1 или 2 (по подразбиране 1): " mode_choice

MODE_BETWEEN_ONLY=0
if [[ "$mode_choice" == "2" ]]; then
  MODE_BETWEEN_ONLY=1
fi

echo
step "=== Стартиране на сканирането... ==="
echo

##### БЛОК 5 #####

# -------------------------------
# СТЪПКА 1: СЪБИРАНЕ НА ФАЙЛОВЕ
# -------------------------------
STEP1_START=$(date +%s)
step "Събирам файлове..." | tee -a "$LOG"

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
      # Филтър по разширения, pattern-и, MIME, категории, regex, дата, размер, директория, дължина на име
      if (( ${#EXTENSIONS[@]} > 0 || ${#PATTERNS_POSITIVE[@]} > 0 || ${#PATTERNS_NEGATIVE[@]} > 0 ||
            ${#MIME_TYPES[@]} > 0 || ${#CATEGORIES[@]} > 0 || ${#REGEX_PATTERNS[@]} > 0 ||
            ${#DATE_FILTERS[@]} > 0 || ${#SIZE_FILTERS[@]} > 0 || ${#DIR_FILTERS[@]} > 0 ||
            ${#NAME_LEN_FILTERS[@]} > 0 )); then
      
          filename=$(basename "$F")
      
          # 1) Отрицателни pattern-и (ако съвпадне → блокира)
          shopt -s nocasematch
          for np in "${PATTERNS_NEGATIVE[@]}"; do
              # Потребителските pattern-и умишлено се ползват като glob-и.
              # shellcheck disable=SC2053
              if [[ "$F" == $np || "$filename" == $np ]]; then
                  shopt -u nocasematch
                  continue 2
              fi
          done
          shopt -u nocasematch
      
          # 2) Позитивни pattern-и (OR)
          if (( ${#PATTERNS_POSITIVE[@]} > 0 )); then
              matched_pos=0
              shopt -s nocasematch
              for pp in "${PATTERNS_POSITIVE[@]}"; do
                  # Потребителските pattern-и умишлено се ползват като glob-и.
                  # shellcheck disable=SC2053
                  if [[ "$F" == $pp || "$filename" == $pp ]]; then
                      matched_pos=1
                      break
                  fi
              done
              shopt -u nocasematch
              (( matched_pos == 0 )) && continue
          fi
      
          # 3) Regex (OR)
          if (( ${#REGEX_PATTERNS[@]} > 0 )); then
              matched_regex=0
              for rx in "${REGEX_PATTERNS[@]}"; do
                  if [[ "$F" =~ $rx ]]; then
                      matched_regex=1
                      break
                  fi
              done
              (( matched_regex == 0 )) && continue
          fi

          # 4) MIME типове (OR)
          if (( ${#MIME_TYPES[@]} > 0 )); then
              mime=$(file --mime-type -b "$F")
              matched_mime=0
              for mt in "${MIME_TYPES[@]}"; do
                  if [[ "$mime" == "$mt" ]]; then
                      matched_mime=1
                      break
                  fi
              done
              (( matched_mime == 0 )) && continue
          fi
      
          # 5) Категории (OR)
          if (( ${#CATEGORIES[@]} > 0 )); then
              mime=$(file --mime-type -b "$F")
              matched_cat=0
              for c in "${CATEGORIES[@]}"; do
                  case "$c" in
                      audio) [[ "$mime" == audio/* ]] && matched_cat=1 ;;
                      video) [[ "$mime" == video/* ]] && matched_cat=1 ;;
                      images) [[ "$mime" == image/* ]] && matched_cat=1 ;;
                      documents) [[ "$mime" == application/* || "$mime" == text/* ]] && matched_cat=1 ;;
                  esac
              done
              (( matched_cat == 0 )) && continue
          fi
      
          # 6) Разширения (OR), само ако няма позитивни pattern-и
          if (( ${#PATTERNS_POSITIVE[@]} == 0 && ${#EXTENSIONS[@]} > 0 )); then
              ext="${filename##*.}"
              [[ "$filename" == "$ext" ]] && continue
              ext_lc=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
              matched_ext=0
              for e in "${EXTENSIONS[@]}"; do
                  if [[ "$ext_lc" == "$e" ]]; then
                      matched_ext=1
                      break
                  fi
              done
              (( matched_ext == 0 )) && continue
          fi
      
          # 7) Филтър по дата (AND)
          if (( ${#DATE_FILTERS[@]} > 0 )); then
              mtime=$(stat -c %Y "$F")
              for df in "${DATE_FILTERS[@]}"; do
                  op="${df:4:1}"
                  val="${df:5}"
                  ts=$(date -d "$val" +%s 2>/dev/null || echo 0)
                  case "$op" in
                      ">")  (( mtime <= ts )) && continue 2 ;;
                      "<")  (( mtime >= ts )) && continue 2 ;;
                  esac
              done
          fi
      
          # 8) Филтър по размер (AND)
          if (( ${#SIZE_FILTERS[@]} > 0 )); then
              size=$(stat -c %s "$F")
              for sf in "${SIZE_FILTERS[@]}"; do
                  op="${sf:4:1}"
                  val="${sf:5}"
                  bytes=$(numfmt --from=iec "$val" 2>/dev/null || echo 0)
                  case "$op" in
                      ">")  (( size <= bytes )) && continue 2 ;;
                      "<")  (( size >= bytes )) && continue 2 ;;
                  esac
              done
          fi
      
          # 9) Филтър по директория (AND)
          if (( ${#DIR_FILTERS[@]} > 0 )); then
              for df in "${DIR_FILTERS[@]}"; do
                  [[ "$F" == $df* ]] || continue 2
              done
          fi
      
          # 10) Филтър по дължина на име (AND)
          if (( ${#NAME_LEN_FILTERS[@]} > 0 )); then
              len=${#filename}
              for nf in "${NAME_LEN_FILTERS[@]}"; do
                  op="${nf:9:1}"
                  val="${nf:10}"
                  case "$op" in
                      ">")  (( len <= val )) && continue 2 ;;
                      "<")  (( len >= val )) && continue 2 ;;
                  esac
              done
          fi
      fi

      size=$(stat -c%s -- "$F" 2>/dev/null || info "")
      [[ -z "$size" ]] && continue

      ALL_FILES+=("$F")
      ALL_FILES_SOURCE+=("$P")
      ALL_FILES_SIZE+=("$size")
    done < <("${CMD[@]}" -print0 2>/dev/null)

    count_after=${#ALL_FILES[@]}
    info "Път '$P': добавени $((count_after - count_before)) файла." | tee -a "$LOG"
  else
    warn "Предупреждение: '$P' не е валидна директория, пропускам." | tee -a "$LOG"
  fi
done

TOTAL=${#ALL_FILES[@]}
success "Общо намерени файлове: $TOTAL" | tee -a "$LOG"

STEP1_END=$(date +%s)
step1_secs=$(time_diff "$STEP1_START" "$STEP1_END")
success "Стъпка 1 (събиране на файлове) време: $(format_duration "$step1_secs")" | tee -a "$LOG"

echo

if (( TOTAL == 0 )); then
  error "Няма файлове по зададените критерии. Прекратяване."
  exit 0
fi

##### БЛОК 6 #####

# -------------------------------
# СТЪПКА 2: ГРУПИРАНЕ ПО РАЗМЕР
# -------------------------------
STEP2_START=$(date +%s)
info "Групиране по размер..." | tee -a "$LOG"

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

info "Размери с повече от един файл: ${#MATCHING_SIZE_GROUPS[@]}" | tee -a "$LOG"

STEP2_END=$(date +%s)
step2_secs=$(time_diff "$STEP2_START" "$STEP2_END")
success "Стъпка 2 (групиране по размер) време: $(format_duration "$step2_secs")" | tee -a "$LOG"
echo

##### БЛОК 7 #####

# -------------------------------
# СТЪПКА 3: ХЕШИРАНЕ НА СЪВПАДАЩИ РАЗМЕРИ
# -------------------------------
STEP3_START=$(date +%s)
step "Хеширане на файлове със съвпадащи размери..." | tee -a "$LOG"

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

success -ne "\nХеширане: завършено.\n" | tee -a "$LOG"

STEP3_END=$(date +%s)
step3_secs=$(time_diff "$STEP3_START" "$STEP3_END")
success "Стъпка 3 (хеширане) време: $(format_duration "$step3_secs")" | tee -a "$LOG"
echo

##### БЛОК 8 #####

# -------------------------------
# СТЪПКА 4: ТЪРСЕНЕ НА ДУБЛИКАТИ + REPORTS
# -------------------------------
STEP4_START=$(date +%s)
step "Откриване на дубликати и генериране на отчети..." | tee -a "$LOG"

# CSV заглавие
echo "hash,size_bytes,size_human,location" > "$CSV"

# HTML общ JS (сортиране + сгъване)
read -r -d '' HTML_COMMON_HEAD <<'EOF'
<script>
function sortTable(tableId, colIndex, numeric, dataAttr) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.querySelectorAll('tr.group-row, tr.group-header'));
  const groups = {};

  // групиране на редовете по data-group
  rows.forEach(row => {
    const g = row.getAttribute('data-group');
    if (!g) return;
    if (!groups[g]) groups[g] = [];
    groups[g].push(row);
  });

  // правим масив от [groupId, sampleRow, sortValue]
  const groupArray = Object.keys(groups).map(gid => {
    const groupRows = groups[gid];
    // за група използваме първия ред за извличане на стойността
    const sample = groupRows[0];
    let cell = sample.children[colIndex];
    let value = '';
    if (dataAttr) {
      value = sample.getAttribute(dataAttr) || '';
    } else if (cell) {
      value = cell.innerText || cell.textContent || '';
    }
    let sortValue = value;
    if (numeric) {
      sortValue = parseFloat(value.replace(/[^0-9.\-]/g,'')) || 0;
    }
    return { gid, rows: groupRows, sortValue };
  });

  // проверяваме посоката (toggle asc/desc)
  const header = table.tHead.rows[0].cells[colIndex];
  const currentDir = header.getAttribute('data-sort-dir') || 'asc';
  const newDir = currentDir === 'asc' ? 'desc' : 'asc';
  header.setAttribute('data-sort-dir', newDir);

  groupArray.sort((a, b) => {
    if (a.sortValue < b.sortValue) return newDir === 'asc' ? -1 : 1;
    if (a.sortValue > b.sortValue) return newDir === 'asc' ? 1 : -1;
    return 0;
  });

  // изчистваме tbody и връщаме редовете по нов ред
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  groupArray.forEach(g => {
    g.rows.forEach(r => tbody.appendChild(r));
  });
}

function toggleGroup(tableId, groupId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const rows = table.tBodies[0].querySelectorAll('tr[data-group="'+groupId+'"]');
  rows.forEach(row => {
    if (row.classList.contains('group-header')) return;
    row.style.display = (row.style.display === 'none') ? '' : 'none';
  });
}

function initTable(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const headers = table.tHead.rows[0].cells;
  // 0: # (група) – сгъване/разгъване, не сортираме
  // 1: Hash – текст
  // 2: Size – numeric (ползваме data-size-bytes)
  // 3: Location – текст
  // 4: Отвори файл – не сортираме
  // 5: Nemo – не сортираме
  if (headers[1]) headers[1].onclick = () => sortTable(tableId, 1, false, null);
  if (headers[2]) headers[2].onclick = () => sortTable(tableId, 2, true, 'data-size-bytes');
  if (headers[3]) headers[3].onclick = () => sortTable(tableId, 3, false, null);
}
</script>
EOF

# HTML (light) – начало
cat > "$HTML_LIGHT" <<EOF
<html>
<head>
<meta charset="UTF-8">
<title>Отчет за дубликати (светла тема)</title>
<style>
body { font-family: sans-serif; background-color: #ffffff; color: #000000; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #cccccc; padding: 4px 6px; font-size: 13px; }
th { background-color: #f0f0f0; cursor: pointer; }
code { font-size: 11px; }
tr.group-header { background-color: #e8f4ff; }
tr.group-row { background-color: #ffffff; }
</style>
$HTML_COMMON_HEAD
</head>
<body onload="initTable('dupTableLight')">
<h1>Отчет за дубликати (светла тема)</h1>
<p>Клик върху # → сгъване/разгъване на група. Клик върху заглавия Hash / Size / Location → сортиране.</p>
<table id="dupTableLight">
<thead>
<tr>
  <th>#</th>
  <th>Hash</th>
  <th>Size</th>
  <th>Location</th>
  <th>Отвори файл</th>
  <th>Nemo команда (първите 2)</th>
</tr>
</thead>
<tbody>
EOF

# HTML (dark) – начало
cat > "$HTML_DARK" <<EOF
<html>
<head>
<meta charset="UTF-8">
<title>Отчет за дубликати (тъмна тема)</title>
<style>
body { font-family: sans-serif; background-color: #1e1e1e; color: #e0e0e0; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #444444; padding: 4px 6px; font-size: 13px; }
th { background-color: #333333; cursor: pointer; }
a { color: #8ab4ff; }
code { font-size: 11px; color: #c0c0c0; }
tr.group-header { background-color: #2f3b4d; }
tr.group-row { background-color: #1e1e1e; }
</style>
$HTML_COMMON_HEAD
</head>
<body onload="initTable('dupTableDark')">
<h1>Отчет за дубликати (тъмна тема)</h1>
<p>Клик върху # → сгъване/разгъване на група. Клик върху заглавия Hash / Size / Location → сортиране.</p>
<table id="dupTableDark">
<thead>
<tr>
  <th>#</th>
  <th>Hash</th>
  <th>Size</th>
  <th>Location</th>
  <th>Отвори файл</th>
  <th>Nemo команда (първите 2)</th>
</tr>
</thead>
<tbody>
EOF

# TXT (delete list)
: > "$DELETE_LIST"

# Инициализация на bash скрипта за изтриване
{
  echo "#!/usr/bin/env bash"
  title "# Генериран от ultimate_duplicate_finder_improved.sh на $TS"
  warn "# ВНИМАНИЕ: прегледай внимателно преди да изпълниш!"
  echo
} > "$DELETE_SCRIPT"
chmod +x "$DELETE_SCRIPT"

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

    # Nemo команда за първите два файла
    nemo_cmd=""
    if ((${#files[@]} >= 2)); then
      f1="${files[0]}"
      f2="${files[1]}"
      nemo_cmd="nemo --no-desktop --browser --select \"$f1\" & nemo --no-desktop --browser --select \"$f2\" &"
    fi

    # TXT – заглавие на групата
    echo "=== Група #$duplicate_group_count | Hash: $h ===" >> "$DELETE_LIST"

    # CSV + HTML + TXT
    for i in "${!files[@]}"; do
      f="${files[$i]}"
      sz="${sizes[$i]}"
      sz_human=$(human_size "$sz")

      # CSV
      echo "$h,$sz,$sz_human,$f" >> "$CSV"

      # TXT – файл + размер
      echo "$f  |  $sz_human" >> "$DELETE_LIST"

      # DELETE SCRIPT – интерактивно изтриване
      printf 'rm -i "%s"\n' "$f" >> "$DELETE_SCRIPT"

      # HTML подготовка
      esc_path=$(printf '%s\n' "$f" | html_escape)
      url_enc=$(url_encode_path "$f")

      # първият ред от групата е header
      if [[ $i -eq 0 ]]; then
        # LIGHT
        echo "<tr class=\"group-header\" data-group=\"$duplicate_group_count\" data-size-bytes=\"$sz\" onclick=\"toggleGroup('dupTableLight','$duplicate_group_count')\">" >> "$HTML_LIGHT"
        echo "<td>$duplicate_group_count</td><td>$h</td><td>$sz_human</td><td>$esc_path</td><td><a href=\"file://$url_enc\">Отвори</a></td><td><code>$nemo_cmd</code></td></tr>" >> "$HTML_LIGHT"
        # DARK
        echo "<tr class=\"group-header\" data-group=\"$duplicate_group_count\" data-size-bytes=\"$sz\" onclick=\"toggleGroup('dupTableDark','$duplicate_group_count')\">" >> "$HTML_DARK"
        echo "<td>$duplicate_group_count</td><td>$h</td><td>$sz_human</td><td>$esc_path</td><td><a href=\"file://$url_enc\">Отвори</a></td><td><code>$nemo_cmd</code></td></tr>" >> "$HTML_DARK"
      else
        # LIGHT
        echo "<tr class=\"group-row\" data-group=\"$duplicate_group_count\" data-size-bytes=\"$sz\">" >> "$HTML_LIGHT"
        echo "<td>$duplicate_group_count</td><td>$h</td><td>$sz_human</td><td>$esc_path</td><td><a href=\"file://$url_enc\">Отвори</a></td><td></td></tr>" >> "$HTML_LIGHT"
        # DARK
        echo "<tr class=\"group-row\" data-group=\"$duplicate_group_count\" data-size-bytes=\"$sz\">" >> "$HTML_DARK"
        echo "<td>$duplicate_group_count</td><td>$h</td><td>$sz_human</td><td>$esc_path</td><td><a href=\"file://$url_enc\">Отвори</a></td><td></td></tr>" >> "$HTML_DARK"
      fi
    done

    echo >> "$DELETE_LIST"
  fi
done

# Затваряне на HTML файловете
echo "</tbody></table></body></html>" >> "$HTML_LIGHT"
echo "</tbody></table></body></html>" >> "$HTML_DARK"

STEP4_END=$(date +%s)
step4_secs=$(time_diff "$STEP4_START" "$STEP4_END")
step "Стъпка 4 (дубликати + отчети) време: $(format_duration "$step4_secs")" | tee -a "$LOG"
info "Намерени групи дубликати: $duplicate_group_count" | tee -a "$LOG"
echo

##### БЛОК 9 #####

# -------------------------------
# TOTAL TIME
# -------------------------------
SCRIPT_END=$(date +%s)
TOTAL_TIME_SECS=$(time_diff "$SCRIPT_START" "$SCRIPT_END")
TOTAL_TIME_FMT=$(format_duration "$TOTAL_TIME_SECS")

info "Общо време за изпълнение: ${TOTAL_TIME_FMT}" | tee -a "$LOG"
echo
title "=== Готово! ==="
success "Общо време за изпълнение: ${TOTAL_TIME_FMT} сек."
info "Отчетите са създадени в текущата директория:"
info " - $CSV"
info " - $HTML_LIGHT"
info " - $HTML_DARK"
info " - $LOG"
info " - $DELETE_LIST (само списък, скриптът НЕ трие нищо)"
echo
