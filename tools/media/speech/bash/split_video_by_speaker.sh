#!/bin/bash
# scripts-toolbox: entrypoint
# scripts-toolbox: command=split_video_by_speaker_sh
# Предназначение: изрязва video сегменти по говорители според transcript timestamp-и.

TRANSCRIPT="$1"
VIDEO="$2"
PAUSE=0  # 0 = без пауза

if [[ -z "$TRANSCRIPT" || -z "$VIDEO" ]]; then
    echo "Употреба: ./split_by_speaker.sh transcript.txt video.mp4"
    exit 1
fi

VIDEO_EXT="${VIDEO##*.}"
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO")

declare -a SPEAKERS
declare -a STARTS

# Четене на транскрипта
while IFS= read -r line; do
    if [[ "$line" =~ ^(.+)[[:space:]]—[[:space:]]([0-9:]+)$ ]]; then
        NAME="${BASH_REMATCH[1]}"
        TIME="${BASH_REMATCH[2]}"
        SPEAKERS+=("$NAME")
        STARTS+=("$TIME")
    fi
done < "$TRANSCRIPT"

# Генериране на сегменти
for idx in "${!SPEAKERS[@]}"; do
    SPEAKER="${SPEAKERS[$idx]}"
    SAFE="${SPEAKER// /_}"

    LIST="${SAFE}_concat.txt"
    : > "$LIST"

    for i in "${!SPEAKERS[@]}"; do
        if [[ "${SPEAKERS[$i]}" == "$SPEAKER" ]]; then
            START="${STARTS[$i]}"

            if (( i < ${#SPEAKERS[@]} - 1 )); then
                END="${STARTS[$((i+1))]}"
                D=$(echo "$(date -d "$END" +%s) - $(date -d "$START" +%s)" | bc)
            else
                # последна реплика → до края на видеото
                SSEC=$(date -d "$START" +%s)
                D=$(echo "$DURATION - $SSEC" | bc)
            fi

            OUT="${SAFE}_${i}.${VIDEO_EXT}"
            ffmpeg -y -ss "$START" -t "$D" -i "$VIDEO" -c copy "$OUT"
            echo "file '$OUT'" >> "$LIST"

            if (( PAUSE > 0 )); then
                PAUSEFILE="${SAFE}_pause_${i}.${VIDEO_EXT}"
                ffmpeg -y -f lavfi -i color=black:s=1920x1080:d=$PAUSE \
                       -f lavfi -i anullsrc -shortest "$PAUSEFILE"
                echo "file '$PAUSEFILE'" >> "$LIST"
            fi
        fi
    done

    FINAL="${SAFE}_video.${VIDEO_EXT}"

    if (( PAUSE == 0 )); then
        ffmpeg -y -f concat -safe 0 -i "$LIST" -c copy "$FINAL"
    else
        ffmpeg -y -f concat -safe 0 -i "$LIST" -c:v libx264 -c:a aac "$FINAL"
    fi

    echo "Готово: $FINAL"
done
