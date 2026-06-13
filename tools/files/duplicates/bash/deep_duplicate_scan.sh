#!/bin/bash
# scripts-toolbox: entrypoint

# ==========================
# КОНФИГУРАЦИЯ
# ==========================
DISK1="${DISK1:-/mnt/external/disk1}"
DISK2="${DISK2:-/mnt/external/disk2}"

LOG="scan.log"
CSV="duplicates_report.csv"
HTML="duplicates_report.html"

echo "=== Сканирането за дубликати започна ===" | tee "$LOG"
date | tee -a "$LOG"

# ==========================
# ФУНКЦИЯ ЗА ПРОГРЕС
# ==========================
progress() {
    local current=$1
    local total=$2
    local percent=$(( 100 * current / total ))
    echo -ne "Прогрес: $percent% ($current/$total) \r"
}

# ==========================
# СТЪПКА 1: СЪБИРАНЕ НА СПИСЪЦИ С ФАЙЛОВЕ
# ==========================
echo "Събирам списък с файлове..." | tee -a "$LOG"

mapfile -t FILES1 < <(find "$DISK1" -type f)
mapfile -t FILES2 < <(find "$DISK2" -type f)

TOTAL=$(( ${#FILES1[@]} + ${#FILES2[@]} ))
COUNT=0

# ==========================
# СТЪПКА 2: СЪЗДАВАНЕ НА КАРТИ ПО РАЗМЕР
# ==========================
declare -A SIZE_MAP1
declare -A SIZE_MAP2

echo "Анализирам размерите..." | tee -a "$LOG"

for f in "${FILES1[@]}"; do
    size=$(stat -c%s "$f")
    SIZE_MAP1["$size"]+="$f;"
    ((COUNT++)); progress "$COUNT" "$TOTAL"
done

for f in "${FILES2[@]}"; do
    size=$(stat -c%s "$f")
    SIZE_MAP2["$size"]+="$f;"
    ((COUNT++)); progress "$COUNT" "$TOTAL"
done

echo -e "\nРазмерите са анализирани." | tee -a "$LOG"

# ==========================
# СТЪПКА 3: ХЕШИРАНЕ САМО НА СЪВПАДАЩИ РАЗМЕРИ
# ==========================
echo "Хеширам файлове със съвпадащи размери..." | tee -a "$LOG"

declare -A HASH_MAP1
declare -A HASH_MAP2

hash_file() {
    sha256sum "$1" | awk '{print $1}'
}

COUNT=0
MATCHING_SIZES=()

# Намери размери, които се срещат и в двата дяла
for size in "${!SIZE_MAP1[@]}"; do
    if [[ -n "${SIZE_MAP2[$size]}" ]]; then
        MATCHING_SIZES+=("$size")
    fi
done

TOTAL=${#MATCHING_SIZES[@]}

for size in "${MATCHING_SIZES[@]}"; do
    IFS=';' read -ra list1 <<< "${SIZE_MAP1[$size]}"
    IFS=';' read -ra list2 <<< "${SIZE_MAP2[$size]}"

    for f in "${list1[@]}"; do
        [[ -f "$f" ]] && HASH_MAP1["$(hash_file "$f")"]+="$f;"
    done

    for f in "${list2[@]}"; do
        [[ -f "$f" ]] && HASH_MAP2["$(hash_file "$f")"]+="$f;"
    done

    ((COUNT++)); progress "$COUNT" "$TOTAL"
done

echo -e "\nХеширането е завършено." | tee -a "$LOG"

# ==========================
# СТЪПКА 4: ТЪРСЕНЕ НА ДУБЛИКАТИ
# ==========================
echo "Откривам дубликати..." | tee -a "$LOG"

: > duplicates_in_disk1.txt
: > duplicates_in_disk2.txt
: > duplicates_between_partitions.txt
: > "$CSV"

echo "hash,location" >> "$CSV"

for hash in "${!HASH_MAP1[@]}"; do
    IFS=';' read -ra list <<< "${HASH_MAP1[$hash]}"
    if (( ${#list[@]} > 1 )); then
        echo "=== Дубликати в първия дял ===" >> duplicates_in_disk1.txt
        for f in "${list[@]}"; do
            echo "$hash  $f" >> duplicates_in_disk1.txt
            echo "$hash,$f" >> "$CSV"
        done
    fi
done

for hash in "${!HASH_MAP2[@]}"; do
    IFS=';' read -ra list <<< "${HASH_MAP2[$hash]}"
    if (( ${#list[@]} > 1 )); then
        echo "=== Дубликати във втория дял ===" >> duplicates_in_disk2.txt
        for f in "${list[@]}"; do
            echo "$hash  $f" >> duplicates_in_disk2.txt
            echo "$hash,$f" >> "$CSV"
        done
    fi
done

for hash in "${!HASH_MAP1[@]}"; do
    if [[ -n "${HASH_MAP2[$hash]}" ]]; then
        echo "=== Дубликати между дяловете ===" >> duplicates_between_partitions.txt
        IFS=';' read -ra list1 <<< "${HASH_MAP1[$hash]}"
        IFS=';' read -ra list2 <<< "${HASH_MAP2[$hash]}"

        for f in "${list1[@]}"; do
            echo "$hash  $f" >> duplicates_between_partitions.txt
            echo "$hash,$f" >> "$CSV"
        done
        for f in "${list2[@]}"; do
            echo "$hash  $f" >> duplicates_between_partitions.txt
            echo "$hash,$f" >> "$CSV"
        done
    fi
done

# ==========================
# СТЪПКА 5: HTML ОТЧЕТ
# ==========================
echo "<html><body><h1>Отчет за дубликати</h1><table border=1>" > "$HTML"
echo "<tr><th>Hash</th><th>Location</th></tr>" >> "$HTML"

tail -n +2 "$CSV" | while IFS=',' read -r hash loc; do
    echo "<tr><td>$hash</td><td>$loc</td></tr>" >> "$HTML"
done

echo "</table></body></html>" >> "$HTML"

echo "Готово! Отчетите са създадени." | tee -a "$LOG"
