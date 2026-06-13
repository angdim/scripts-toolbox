#!/usr/bin/env bash
# scripts-toolbox: entrypoint

show_help() {
cat <<EOF
Употреба: $0 [опции] /път/към/директория

Опции:
  -h, --help        Показва това ръководство
  -o FILE           Име на изходния playlist (по подразбиране: playlist.m3u8 в root)
  --audio-only      Само аудио файлове
  --video-only      Само видео файлове
  --group           Плейлист за всяка директория
  --master          Master playlist, който включва всички под-плейлисти
  --extinf          Добавя #EXTINF метаданни

Пример:
  $0 ~/Videos
  $0 --group --master ~/Media
EOF
}

OUTFILE=""
AUDIO_ONLY=0
VIDEO_ONLY=0
GROUP=0
MASTER=0
EXTINF=0

while [[ "$1" != "" ]]; do
    case "$1" in
        -h|--help) show_help; exit 0 ;;
        -o) shift; OUTFILE="$1" ;;
        --audio-only) AUDIO_ONLY=1 ;;
        --video-only) VIDEO_ONLY=1 ;;
        --group) GROUP=1 ;;
        --master) MASTER=1 ;;
        --extinf) EXTINF=1 ;;
        *) TARGET_DIR="$1" ;;
    esac
    shift
done

if [[ -z "$TARGET_DIR" ]]; then
    show_help
    exit 1
fi

TARGET_DIR=$(realpath "$TARGET_DIR")

VIDEO_EXT="mp4|mkv|webm|avi|mov"
AUDIO_EXT="mp3|wav|flac|aac|ogg"

if [[ $AUDIO_ONLY -eq 1 ]]; then
    EXT_PATTERN="$AUDIO_EXT"
elif [[ $VIDEO_ONLY -eq 1 ]]; then
    EXT_PATTERN="$VIDEO_EXT"
else
    EXT_PATTERN="$VIDEO_EXT|$AUDIO_EXT"
fi

generate_playlist() {
    local dir="$1"
    local outfile="$2"

    echo "#EXTM3U" > "$outfile"

    find "$dir" -type f \
        | grep -E "\.[a-zA-Z0-9]{2,5}$" \
        | grep -Ei "\.($EXT_PATTERN)$" \
        | sort -f \
        | while IFS= read -r file; do
            rel="${file#"$TARGET_DIR"/}"   # ← запазва оригиналното име и структура
            if [[ $EXTINF -eq 1 ]]; then
                name=$(basename "$file")
                echo "#EXTINF:-1,$name" >> "$outfile"
            fi
            echo "$rel" >> "$outfile"
        done
}

if [[ $GROUP -eq 1 ]]; then
    PLAYLISTS=()

    while IFS= read -r dir; do
        pl="$dir/playlist.m3u8"
        generate_playlist "$dir" "$pl"
        PLAYLISTS+=("$pl")
    done < <(find "$TARGET_DIR" -type d | sort -f)

    if [[ $MASTER -eq 1 ]]; then
        MASTER_FILE="${OUTFILE:-$TARGET_DIR/master_playlist.m3u8}"
        echo "#EXTM3U" > "$MASTER_FILE"
        for pl in "${PLAYLISTS[@]}"; do
            rel="${pl#"$TARGET_DIR"/}"
            echo "$rel" >> "$MASTER_FILE"
        done
        echo "Master playlist: $MASTER_FILE"
    fi

    exit 0
fi

OUT="${OUTFILE:-$TARGET_DIR/playlist.m3u8}"
generate_playlist "$TARGET_DIR" "$OUT"
echo "Готово! Създаден е playlist: $OUT"
