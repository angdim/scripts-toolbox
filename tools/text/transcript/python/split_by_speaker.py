#!/usr/bin/env python3
# scripts-toolbox: entrypoint
# no-venv
"""
Разделя transcript по говорители и може да генерира общ файл, отделни файлове, JSON и timestamp списъци.
"""

import argparse
import json
import re
import sys
from pathlib import Path

TIME_PATTERN = r"\d{2}:\d{2}:\d{2}"
SPEAKER_PATTERN = r"[^:]+"
LINE_RE = re.compile(
    rf"^\[(?P<time>{TIME_PATTERN})\]\s+(?P<speaker>{SPEAKER_PATTERN}):\s*(?P<text>.*)$"
)


def get_script_help():
    return """Цел:
  Обработва transcript файл във формат:
    [HH:MM:SS] Име на говорител: текст

Начин на работа:
  1. Чете входния файл ред по ред.
  2. Пропуска празни редове.
  3. Обединява последователни реплики на един и същ говорител в един абзац.
  4. Запазва началното време от първата реплика в обединения абзац.
  5. Може да създаде общ файл, отделни файлове по говорители, JSON метаданни
     и timestamp списъци за видео обработка.

Режими:
  Без опции   Създава само combined.txt.
  --split     Създава само файлове по говорители.
  --both      Създава combined.txt и файлове по говорители.

Примери:
  split_by_speaker.py input.txt
  split_by_speaker.py input.txt --split --output-dir speakers
  split_by_speaker.py input.txt --both --json --video --output-dir result
  split_by_speaker.py input.txt --combined-name merged.txt
"""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Разделя transcript по говорители.",
        epilog=get_script_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="Transcript файл")
    parser.add_argument("--split", action="store_true", help="Създава само отделни файлове по говорители")
    parser.add_argument("--both", action="store_true", help="Създава общ файл и отделни файлове по говорители")
    parser.add_argument("--output-dir", default=".", help="Директория за резултатите. По подразбиране: текущата директория")
    parser.add_argument("--combined-name", default="combined.txt", help="Име на общия файл. По подразбиране: combined.txt")
    parser.add_argument("--json", action="store_true", help="Извежда JSON метаданни към stdout")
    parser.add_argument("--normalize", action="store_true", help="Нормализира имена от тип SPK_01 към SPK_1")
    parser.add_argument("--video", action="store_true", help="Създава timestamp списъци за всеки говорител")
    parser.add_argument("--log", help="Лог файл")
    return parser.parse_args(argv)


def normalize_speaker(speaker):
    return re.sub(r"_0+([0-9])", r"_\1", speaker)


def safe_filename(name):
    safe = "".join(c for c in name.replace(" ", "_") if c.isalnum() or c == "_")
    return safe or "unknown_speaker"


def parse_transcript(lines, normalize=False):
    speakers = {}
    times = {}
    counts = {}
    combined_blocks = []

    current_speaker = None
    current_time = None
    current_text = []

    def ensure_speaker(speaker):
        if speaker not in speakers:
            speakers[speaker] = []
            times[speaker] = []
            counts[speaker] = 0

    def flush_current():
        if current_speaker is None:
            return

        text = " ".join(part.strip() for part in current_text if part.strip())
        if not text:
            return

        block = f"[{current_time}] {current_speaker}: {text}"
        combined_blocks.append((current_time, current_speaker, block))
        speakers[current_speaker].append(block)

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

        if normalize:
            speaker = normalize_speaker(speaker)

        ensure_speaker(speaker)

        if speaker != current_speaker:
            flush_current()
            current_speaker = speaker
            current_time = time
            current_text = [text]
            times[speaker].append(time)
            counts[speaker] += 1
        else:
            current_text.append(text)

    flush_current()
    return combined_blocks, speakers, times, counts


def write_combined(combined_blocks, outdir, filename):
    combined = outdir / filename
    with combined.open("w", encoding="utf-8") as f:
        for _, _, block in combined_blocks:
            f.write(block + "\n\n")
    return combined


def write_speaker_files(speakers, outdir):
    written = {}
    used_names = set()

    for speaker, blocks in speakers.items():
        base = safe_filename(speaker)
        filename = f"{base}.txt"
        counter = 2

        while filename in used_names:
            filename = f"{base}_{counter}.txt"
            counter += 1

        used_names.add(filename)
        outfile = outdir / filename
        with outfile.open("w", encoding="utf-8") as f:
            for block in blocks:
                f.write(block + "\n\n")

        written[speaker] = outfile

    return written


def write_video_lists(times, outdir):
    written = {}
    used_names = set()

    for speaker, speaker_times in times.items():
        base = safe_filename(speaker)
        filename = f"{base}_video_list.txt"
        counter = 2

        while filename in used_names:
            filename = f"{base}_video_list_{counter}.txt"
            counter += 1

        used_names.add(filename)
        outfile = outdir / filename
        with outfile.open("w", encoding="utf-8") as f:
            for time in speaker_times:
                f.write(time + "\n")

        written[speaker] = outfile

    return written


def build_metadata(speakers, counts, speaker_files):
    return {
        speaker: {
            "file": speaker_files.get(speaker, Path(f"{safe_filename(speaker)}.txt")).name,
            "count": counts[speaker],
        }
        for speaker in speakers
    }


def write_log(log_path, messages):
    if not log_path:
        return

    with open(log_path, "w", encoding="utf-8") as logfile:
        for message in messages:
            logfile.write(message + "\n")


def main(argv=None):
    args = parse_args(argv)
    input_path = Path(args.input)
    outdir = Path(args.output_dir)
    log_messages = []

    if not input_path.is_file():
        print(f"Грешка: файлът не съществува: {input_path}", file=sys.stderr)
        return 1

    try:
        outdir.mkdir(parents=True, exist_ok=True)
        with input_path.open("r", encoding="utf-8") as f:
            combined_blocks, speakers, times, counts = parse_transcript(f, normalize=args.normalize)

        speaker_files = {}

        if not args.split or args.both:
            combined = write_combined(combined_blocks, outdir, args.combined_name)
            log_messages.append(f"Combined file: {combined}")

        if args.split or args.both:
            speaker_files = write_speaker_files(speakers, outdir)
            for outfile in speaker_files.values():
                log_messages.append(f"Speaker file: {outfile}")

            if args.video:
                video_files = write_video_lists(times, outdir)
                for outfile in video_files.values():
                    log_messages.append(f"Video list: {outfile}")

        if args.json:
            print(json.dumps(build_metadata(
                speakers, counts, speaker_files),
                indent=2, ensure_ascii=False)
            )

        write_log(args.log, log_messages)
    except OSError as exc:
        print(f"Грешка при работа с файл: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Грешка: {exc}", file=sys.stderr)
        return 1

    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
