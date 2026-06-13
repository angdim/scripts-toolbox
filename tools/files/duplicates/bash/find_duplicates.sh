#!/bin/bash
# scripts-toolbox: entrypoint
# Предназначение: търси дублирани файлове в два зададени дяла/директории чрез SHA256 хешове.

# === КОНФИГУРАЦИЯ ===
DISK1="${DISK1:-/mnt/external/disk1}"
DISK2="${DISK2:-/mnt/external/disk2}"

# === ИЗХОДНИ ФАЙЛОВЕ ===
HASH1="disk1_hashes.txt"
HASH2="disk2_hashes.txt"
DUP1="duplicates_in_disk1.txt"
DUP2="duplicates_in_disk2.txt"
BETWEEN="duplicates_between_partitions.txt"

echo "Генерирам SHA256 хешове за първия дял..."
find "$DISK1" -type f -print0 | xargs -0 sha256sum > "$HASH1"

echo "Генерирам SHA256 хешове за втория дял..."
find "$DISK2" -type f -print0 | xargs -0 sha256sum > "$HASH2"

echo "Търся дубликати вътре в първия дял..."
cut -d ' ' -f1 "$HASH1" | sort | uniq -d > dup_hashes_disk1.txt
grep -Ff dup_hashes_disk1.txt "$HASH1" > "$DUP1"

echo "Търся дубликати вътре във втория дял..."
cut -d ' ' -f1 "$HASH2" | sort | uniq -d > dup_hashes_disk2.txt
grep -Ff dup_hashes_disk2.txt "$HASH2" > "$DUP2"

echo "Търся дубликати между двата дяла..."
cut -d ' ' -f1 "$HASH1" | sort > h1.txt
cut -d ' ' -f1 "$HASH2" | sort > h2.txt
comm -12 h1.txt h2.txt > common_hashes.txt

grep -Ff common_hashes.txt "$HASH1" > "$BETWEEN"
grep -Ff common_hashes.txt "$HASH2" >> "$BETWEEN"

echo "Готово!"
echo "Отчетите са:"
echo " - $DUP1"
echo " - $DUP2"
echo " - $BETWEEN"
