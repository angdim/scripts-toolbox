#!/bin/bash
# scripts-toolbox: entrypoint
# scripts-toolbox: command=split_media_by_time_sh
# Предназначение: разделя audio/video файл на части с фиксирана продължителност и overlap.

CHUNK_DURATION=$((29*60))  # 20 минути
OVERLAP=5                  # 10 секунди
PREFIX="part_"

INPUT="${1:-input.mp4}"

if [[ ! -f "$INPUT" ]]; then
    echo "Грешка: Файлът '$INPUT' не съществува."
    exit 1
fi

EXT="${INPUT##*.}"

DURATION=$(ffprobe -v error -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 "$INPUT")
DURATION=${DURATION%.*}

format_time() {
    printf "%02d:%02d:%02d" $(($1/3600)) $(($1%3600/60)) $(($1%60))
}

START=0
PART=1

while [[ $START -lt $DURATION ]]; do
    END=$((START + CHUNK_DURATION))
    if [[ $END -gt $DURATION ]]; then
        END=$DURATION
    fi

    OUTFILE="${PREFIX}$(printf "%02d" $PART).$EXT"

    echo "Създавам част $PART: $(format_time "$START") - $(format_time "$END")"

    ffmpeg -y -ss "$START" -to "$END" -i "$INPUT" -c copy "$OUTFILE"

    if [[ $END -ge $DURATION ]]; then
        # последна част – прекъсваме
        break
    fi

    PART=$((PART + 1))
    START=$((END - OVERLAP))
done

echo "Готово."
