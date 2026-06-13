#!/bin/bash
# scripts-toolbox: entrypoint
# scripts-toolbox: command=video4lexus_sh
# Предназначение: конвертира video файлове към ограничения, подходящи за Lexus infotainment системи.

# Максимални размери за Lexus
MAX_WIDTH=720
MAX_HEIGHT=480

# Създаване на изходна папка
mkdir -p lexus_converted

# Цветно оформление
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Броячи
total=0
success=0
failed=0

echo -e "${YELLOW}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  Lexus RX 450h видео конвертор (smart scaling)    ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════╝${NC}\n"

# Функция за получаване на размерите на видеото
get_video_dimensions() {
    ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$1" 2>/dev/null
}

# Обработка на всички видео файлове
shopt -s nullglob
for file in *.{mp4,avi,mkv,mov,wmv,flv,m4v,MP4,AVI,MKV,MOV,WMV,FLV,M4V}; do
    [ -e "$file" ] || continue
    
    total=$((total + 1))
    filename="${file%.*}"
    
    echo -e "${CYAN}[$total] Конвертирам: $file${NC}"
    
    # Получаване на размерите
    dimensions=$(get_video_dimensions "$file")
    if [ -n "$dimensions" ]; then
        width=$(echo "$dimensions" | cut -d'x' -f1)
        height=$(echo "$dimensions" | cut -d'x' -f2)
        echo -e "  → Оригинален размер: ${width}x${height}"
        
        # Проверка дали е нужно мащабиране
        if [ "$width" -gt "$MAX_WIDTH" ] || [ "$height" -gt "$MAX_HEIGHT" ]; then
            echo -e "  → Мащабиране до максимум ${MAX_WIDTH}x${MAX_HEIGHT}"
            scale_args=(-vf "scale='min($MAX_WIDTH,iw)':'min($MAX_HEIGHT,ih)':force_original_aspect_ratio=decrease")
        else
            echo -e "  → Запазвам оригиналния размер"
            scale_args=()
        fi
    else
        echo -e "  → Неуспешно откриване на размера; продължавам без мащабиране"
        scale_args=()
    fi
    
    # Конвертиране
    if ffmpeg -i "$file" \
      -c:v libx264 -profile:v baseline -level 3.1 \
      "${scale_args[@]}" \
      -b:v 1500k -maxrate 2000k -bufsize 4000k \
      -c:a aac -b:a 192k \
      -movflags +faststart \
      -loglevel error -stats \
      "lexus_converted/${filename}_lexus.mp4"; then
        # Проверка на размера на файла
        output_size=$(stat -f%z "lexus_converted/${filename}_lexus.mp4" 2>/dev/null || stat -c%s "lexus_converted/${filename}_lexus.mp4" 2>/dev/null)
        output_size_mb=$((output_size / 1024 / 1024))
        
        echo -e "${GREEN}✓ Успешно конвертирано: $file (${output_size_mb}MB)${NC}"
        
        if [ "$output_size_mb" -gt 2000 ]; then
            echo -e "${RED}  ⚠ ПРЕДУПРЕЖДЕНИЕ: файлът надвишава FAT32 лимита от 2GB!${NC}"
        fi
        echo ""
        success=$((success + 1))
    else
        echo -e "${RED}✗ Неуспешно конвертиране: $file${NC}\n"
        failed=$((failed + 1))
    fi
done

# Резюме
echo -e "\n${YELLOW}============================================================${NC}"
echo -e "${YELLOW}Резюме на конвертирането:${NC}"
echo -e "${GREEN}  ✓ Успешни: $success${NC}"
echo -e "${RED}  ✗ Неуспешни: $failed${NC}"
echo -e "${YELLOW}  Общо: $total${NC}"
echo -e "${YELLOW}============================================================${NC}"
echo -e "\nКонвертираните файлове са в: ${GREEN}lexus_converted/${NC}\n"
