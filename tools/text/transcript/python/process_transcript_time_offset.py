#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# no-venv
"""
Прилага времево отместване върху transcript timestamp-и и обединява последователни реплики.
"""

import re
import sys
import os

# ==========================
# Парсване на време HH:MM:SS → секунди
# ==========================
def parse_time_to_seconds(t):
    parts = t.split(":")
    if len(parts) != 3:
        raise ValueError("Форматът трябва да е HH:MM:SS")
    h, m, s = [int(p) for p in parts]
    return h * 3600 + m * 60 + s

# ==========================
# Форматиране секунди → HH:MM:SS
# ==========================
def format_seconds(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02}:{m:02}:{s:02}"

# ==========================
# Основна логика
# ==========================
def process_transcript(lines, offset_seconds):
    result = []
    current_speaker = None
    current_time = None
    buffer = []

    # regex за твоя формат:
    # [00:01:14] SPK_1: текст...
    pattern = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+(SPK_\d+):\s*(.*)$")

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        match = pattern.match(line)
        if not match:
            continue  # пропускаме редове, които не съвпадат

        time_str, speaker, text = match.groups()

        # добавяме offset
        original_sec = parse_time_to_seconds(time_str)
        shifted_sec = original_sec + offset_seconds
        shifted_time = format_seconds(shifted_sec)

        # нов говорител → затваряме предишния блок
        if speaker != current_speaker:
            if current_speaker is not None:
                result.append({
                    "speaker": current_speaker,
                    "time": current_time,
                    "text": " ".join(buffer)
                })
            current_speaker = speaker
            current_time = shifted_time
            buffer = [text]
        else:
            buffer.append(text)

    # последен блок
    if current_speaker is not None and buffer:
        result.append({
            "speaker": current_speaker,
            "time": current_time,
            "text": " ".join(buffer)
        })

    return result

# ==========================
# Главна част
# ==========================
if __name__ == "__main__":
    # входен файл
    input_file = sys.argv[1] if len(sys.argv) > 1 else "transcript.txt"

    if not os.path.isfile(input_file):
        print(f"Грешка: Файлът '{input_file}' не съществува.")
        sys.exit(1)

    # offset (ако липсва → 0)
    if len(sys.argv) > 2:
        offset_seconds = parse_time_to_seconds(sys.argv[2])
    else:
        offset_seconds = 0

    # изходен файл
    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_processed{ext}"

    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks = process_transcript(lines, offset_seconds)

    with open(output_file, "w", encoding="utf-8") as out:
        for b in blocks:
            out.write(f"{b['speaker']} — {b['time']}\n")
            out.write(f"{b['text']}\n\n")

    print(f"Готово. Резултатът е записан в: {output_file}")

