#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# no-venv
"""
Извлича репликите на всеки говорител от transcript и създава отделен текстов файл за всеки.
"""

import re
import sys
import os

# Формат:
# Име Фамилия — HH:MM:SS
header_pattern = re.compile(r"^(.+?)\s+—\s+(\d{1,2}:\d{2}:\d{2})$")

def extract_speakers(input_file):
    speakers = {}
    current_speaker = None
    current_time = None
    buffer = []

    with open(input_file, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()

            # Проверка дали редът е заглавие на нова реплика
            match = header_pattern.match(line)
            if match:
                # Ако имаме предишна реплика → записваме я
                if current_speaker and buffer:
                    if current_speaker not in speakers:
                        speakers[current_speaker] = []
                    speakers[current_speaker].append(
                        f"[{current_time}] " + " ".join(buffer)
                    )
                    buffer = []

                # Нов говорител
                current_speaker, current_time = match.groups()
                continue

            # Текстова част
            if line:
                buffer.append(line)

        # Последна реплика
        if current_speaker and buffer:
            if current_speaker not in speakers:
                speakers[current_speaker] = []
            speakers[current_speaker].append(
                f"[{current_time}] " + " ".join(buffer)
            )

    return speakers


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "transcript.txt"

    if not os.path.isfile(input_file):
        print(f"Грешка: Файлът '{input_file}' не съществува.")
        sys.exit(1)

    speakers = extract_speakers(input_file)

    if not speakers:
        print("Не бяха открити говорители. Провери формата на файла.")
        sys.exit(0)

    for speaker, lines in speakers.items():
        safe_name = speaker.replace(" ", "_")
        out_file = f"{safe_name}.txt"

        with open(out_file, "w", encoding="utf-8") as f:
            for entry in lines:
                f.write(entry + "\n\n")  # празен ред между репликите

        print(f"Създаден файл: {out_file}")

    print("Готово.")

