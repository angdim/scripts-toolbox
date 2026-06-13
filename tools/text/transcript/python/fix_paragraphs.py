#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# no-venv
"""
Нормализира transcript абзаци, като обединява редовете на всяка реплика в един чист параграф.
"""

import re
import sys

if len(sys.argv) < 3:
    print("Употреба: fix_paragraphs.py input.txt output.txt")
    sys.exit(1)

input_file = sys.argv[1]
output_file = sys.argv[2]

# Разпознава:
# [00:00:00] Име: текст...
header_re = re.compile(r"^\[([0-9]{2}:[0-9]{2}:[0-9]{2})\]\s+([^:]+):\s*(.*)$")

current_time = None
current_speaker = None
current_text = []

def flush_block(out):
    """Записва текущия абзац в изходния файл."""
    if current_time and current_speaker and current_text:
        merged = " ".join(" ".join(current_text).split())
        out.write(f"[{current_time}] {current_speaker}: {merged}\n\n")

with open(input_file, "r", encoding="utf-8") as f, \
     open(output_file, "w", encoding="utf-8") as out:

    for line in f:
        line = line.rstrip()

        m = header_re.match(line)
        if m:
            # Нов абзац → затваряме стария
            flush_block(out)

            current_time = m.group(1)
            current_speaker = m.group(2).strip()
            first_text = m.group(3).strip()

            current_text = [first_text] if first_text else []
        else:
            # Продължение на абзаца → добавяме реда
            if line.strip():
                current_text.append(line.strip())

    # Финален flush
    flush_block(out)

print("Готово.")
