#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
M4A към MP3 конвертор с аудио обработка чрез FFmpeg.
Конвертира на място: .mp3 файлът се създава до съответния .m4a файл.
"""

import subprocess
import argparse
from pathlib import Path


# ============================================================
#  НАСТРОЙКИ - променяй тук след като намериш добрите параметри
# ============================================================
DEFAULT_SETTINGS = {
    "bitrate": "192k",
    "equalizer": [
        "1000:3:200",
        "2500:4:500",
        "4000:2:300",
    ],
    "highpass": 80,
    "lowpass": 12000,
    "compressor": {
        "enabled": True,
        "threshold": -20,
        "ratio": 3,
        "attack": 5,
        "release": 50,
        "gain": 4,
    },
    "normalize": True,
}
# ============================================================


def build_ffmpeg_filters(settings):
    filters = []
    if settings.get("highpass"):
        filters.append(f"highpass=f={settings['highpass']}")
    if settings.get("lowpass"):
        filters.append(f"lowpass=f={settings['lowpass']}")
    for eq in settings.get("equalizer", []):
        freq, gain, bw = eq.split(":")
        filters.append(f"equalizer=f={freq}:g={gain}:width={bw}:width_type=h")
    comp = settings.get("compressor", {})
    if comp.get("enabled"):
        filters.append(
            f"acompressor="
            f"threshold={comp['threshold']}dB:"
            f"ratio={comp['ratio']}:"
            f"attack={comp['attack']}:"
            f"release={comp['release']}:"
            f"makeup={comp['gain']}dB"
        )
    if settings.get("normalize"):
        filters.append("loudnorm")
    return ",".join(filters) if filters else None


def convert_file(input_path, settings, dry_run=False):
    """Конвертира един файл - изходът е до входния файл."""
    output_path = input_path.with_suffix(".mp3")  # <-- същата директория, същото име

    cmd = ["ffmpeg", "-i", str(input_path), "-y"]
    filter_chain = build_ffmpeg_filters(settings)
    if filter_chain:
        cmd += ["-af", filter_chain]
    cmd += ["-b:a", settings["bitrate"], "-codec:a", "libmp3lame", str(output_path)]

    if dry_run:
        print(f"  [DRY RUN] {input_path} -> {output_path.name}")
        return True

    print(f"  {input_path} -> {output_path.name}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ГРЕШКА: {result.stderr[-300:]}")
            return False
        return True
    except FileNotFoundError:
        print("  ГРЕШКА: ffmpeg не е намерен! Инсталирай с: sudo apt install ffmpeg")
        return False


def main():
    parser = argparse.ArgumentParser(description="M4A -> MP3 конвертор (на място)")
    parser.add_argument("source", help="Директория за търсене на .m4a файлове")
    parser.add_argument("--bitrate", default=DEFAULT_SETTINGS["bitrate"])
    parser.add_argument("--no-eq", action="store_true")
    parser.add_argument("--no-compress", action="store_true")
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = DEFAULT_SETTINGS.copy()
    settings["bitrate"] = args.bitrate
    if args.no_eq:
        settings["equalizer"] = []
    if args.no_compress:
        settings["compressor"]["enabled"] = False
    if args.no_normalize:
        settings["normalize"] = False

    source_dir = Path(args.source)
    if not source_dir.exists():
        print(f"ГРЕШКА: '{source_dir}' не съществува!")
        return

    m4a_files = list(source_dir.rglob("*.m4a"))
    if not m4a_files:
        print("Не са намерени .m4a файлове.")
        return

    print(f"Намерени {len(m4a_files)} файла...\n")

    success, failed = 0, 0
    for i, m4a_file in enumerate(m4a_files, 1):
        print(f"[{i}/{len(m4a_files)}]")
        if convert_file(m4a_file, settings, dry_run=args.dry_run):
            success += 1
        else:
            failed += 1

    print(f"\n✓ Успешно: {success}  ✗ Грешки: {failed}")


if __name__ == "__main__":
    main()

