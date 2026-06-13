#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# no-venv
"""
Обединява последователни transcript реплики на един и същ говорител в общи параграфи.
"""

import argparse
import os
import re
import sys

TIME_PATTERN = r"\d{2}:\d{2}:\d{2}"
SPEAKER_PATTERN = r"[^:]+"
LINE_RE = re.compile(
    rf"^\[(?P<time>{TIME_PATTERN})\]\s+(?P<speaker>{SPEAKER_PATTERN}):\s*(?P<text>.*)$"
)


def get_script_help():
    return """Цел:
  Обединява последователни реплики на един и същ говорител в transcript файл.

Очакван входен формат:
  [HH:MM:SS] Име на говорител: Текст на репликата

Поддържани имена:
  Името на говорителя може да съдържа интервали и Unicode символи, например:
  Tony Merkel
  Nathan Reynolds
  Ангел Маринов Димитров

Начин на работа:
  1. Скриптът чете входния файл ред по ред.
  2. Празните редове се пропускат.
  3. Ако две или повече последователни реплики са от един и същ говорител,
     текстовете им се слепват в един параграф.
  4. За обединения параграф се запазва началното време от първата реплика.
  5. При смяна на говорителя започва нов параграф.

Пример:
  [00:01:10] Tony Merkel: First sentence.
  [00:01:23] Tony Merkel: Second sentence.

  става:
  [00:01:10] Tony Merkel: First sentence. Second sentence.

Използване:
  process_transcript.py input.txt
  process_transcript.py input.txt -o output.txt
"""


def process_transcript(lines):
    """Обединява последователни transcript реплики на един и същ говорител."""
    blocks = []
    current_time = None
    current_speaker = None
    current_text = []

    def flush_current():
        if current_speaker is not None:
            blocks.append({
                "time": current_time,
                "speaker": current_speaker,
                "text": " ".join(part.strip() for part in current_text if part.strip()),
            })

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        match = LINE_RE.match(line)
        if not match:
            raise ValueError(f"Невалиден формат на ред {line_number}: {raw_line.rstrip()}")

        time = match.group("time")
        speaker = match.group("speaker").strip()
        text = match.group("text").strip()

        if speaker != current_speaker:
            flush_current()
            current_time = time
            current_speaker = speaker
            current_text = [text]
        else:
            current_text.append(text)

    flush_current()
    return blocks


def write_blocks(blocks, output_file):
    with open(output_file, "w", encoding="utf-8") as out:
        for block in blocks:
            out.write(f"[{block['time']}] {block['speaker']}: {block['text']}\n\n")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Обединява последователни реплики на един и същ говорител.",
        epilog=get_script_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_file", help="Входен transcript файл")
    parser.add_argument("-o", "--output", help="Изходен файл. По подразбиране: <input>_processed<ext>")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    if not os.path.isfile(args.input_file):
        print(f"Грешка: Файлът '{args.input_file}' не съществува.", file=sys.stderr)
        return 1

    base, ext = os.path.splitext(args.input_file)
    output_file = args.output or f"{base}_processed{ext}"

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            blocks = process_transcript(f)
        write_blocks(blocks, output_file)
    except ValueError as exc:
        print(f"Грешка: {exc}", file=sys.stderr)
        return 1

    print(f"Готово. Резултатът е записан в: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
