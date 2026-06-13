#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
Автоматично разделя audio/video файл на отделни тракове според паузи/тишина.
Използва FFmpeg за откриване на тишина и извличане на отделните части.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
import re

class SilenceSplitter:
    def __init__(self, input_file,
                 silence_threshold=-50,
                 silence_duration=1.0,
                 output_format='mp3',
                 audio_bitrate='192k',
                 video_codec='copy',
                 audio_codec='libmp3lame',
                 name_pattern='track_{num}'):  # НОВО!

        self.input_file = Path(input_file)
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.output_format = output_format
        self.audio_bitrate = audio_bitrate
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.name_pattern = name_pattern  # НОВО!

        self.is_video = self.check_if_video()
        self.output_dir = Path(f"{self.input_file.stem}_tracks")
        self.output_dir.mkdir(exist_ok=True)

    def check_if_video(self):
        """Проверява дали файлът съдържа видео stream"""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            str(self.input_file)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return True
            return False
        except (subprocess.SubprocessError, json.JSONDecodeError):
            return False

    def detect_silence(self):
        """
        Детектира паузи/тишина във файла и връща списък с времена.
        Връща: [(start1, end1), (start2, end2), ...]
        """
        print(f"🔍 Откривам тишина (праг: {self.silence_threshold}dB, минимална продължителност: {self.silence_duration}s)...")

        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-af', f'silencedetect=noise={self.silence_threshold}dB:d={self.silence_duration}',
            '-f', 'null',
            '-'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr

        silence_starts = []
        silence_ends = []

        for line in output.split('\n'):
            if 'silence_start' in line:
                match = re.search(r'silence_start: ([\d.]+)', line)
                if match:
                    silence_starts.append(float(match.group(1)))

            if 'silence_end' in line:
                match = re.search(r'silence_end: ([\d.]+)', line)
                if match:
                    silence_ends.append(float(match.group(1)))

        silences = list(zip(silence_starts, silence_ends))

        print(f"✓ Открити периоди на тишина: {len(silences)}")
        return silences

    def get_duration(self):
        """Получава общата продължителност на файла"""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(self.input_file)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
        except (subprocess.SubprocessError, json.JSONDecodeError, KeyError, ValueError):
            return None

    def calculate_segments(self, silences):
        """
        Изчислява сегментите (траковете) базирано на тишината.
        Връща: [(start1, end1), (start2, end2), ...]
        """
        duration = self.get_duration()

        if not duration:
            print("⚠ Неуспешно определяне на продължителността на файла")
            return []

        segments = []

        if silences:
            segments.append((0, silences[0][0]))

        for i in range(len(silences) - 1):
            start = silences[i][1]
            end = silences[i + 1][0]
            segments.append((start, end))

        if silences:
            segments.append((silences[-1][1], duration))

        segments = [(s, e) for s, e in segments if (e - s) >= 3.0]

        print(f"✓ Изчислени track сегменти: {len(segments)}")
        return segments

    def generate_filename(self, track_num, total_tracks):
        """
        Генерира име на файл според шаблона.

        Поддържани placeholders:
        {num} или {n} - номер на трак (с padding според общия брой)
        {total} или {t} - общ брой тракове
        {name} - име на оригиналния файл (без разширение)

        Примери:
        'track_{num}' → track_01.mp3, track_02.mp3, ...
        '{name}_{num}' → song_01.mp3, song_02.mp3, ...
        'Part_{n}_of_{t}' → Part_01_of_15.mp3, Part_02_of_15.mp3, ...
        'Song {num}' → Song 01.mp3, Song 02.mp3, ...
        """
        # Определяне на padding според броя тракове
        padding = len(str(total_tracks))

        # Замяна на placeholders
        filename = self.name_pattern
        filename = filename.replace('{num}', f'{track_num:0{padding}d}')
        filename = filename.replace('{n}', f'{track_num:0{padding}d}')
        filename = filename.replace('{total}', str(total_tracks))
        filename = filename.replace('{t}', str(total_tracks))
        filename = filename.replace('{name}', self.input_file.stem)

        return f"{filename}.{self.output_format}"

    def extract_segment(self, start, end, output_file, track_num):
        """Извлича един сегмент от файла"""
        duration = end - start

        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-ss', str(start),
            '-t', str(duration),
            '-y'
        ]

        if self.is_video and self.output_format in ['mp4', 'mkv', 'avi', 'mov']:
            cmd.extend([
                '-c:v', self.video_codec,
                '-c:a', self.audio_codec,
                '-b:a', self.audio_bitrate
            ])
        else:
            cmd.extend([
                '-vn',
                '-c:a', self.audio_codec,
                '-b:a', self.audio_bitrate
            ])

        cmd.append(str(output_file))

        print(f"  ⏩ Извличам track {track_num}: {self.format_time(start)} → {self.format_time(end)} ({self.format_time(duration)})")

        result = subprocess.run(cmd, capture_output=True, text=True)

        return result.returncode == 0

    def format_time(self, seconds):
        """Форматира секунди в HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def preview(self):
        """Показва само какви тракове ще се създадат БЕЗ да ги извлича"""
        print(f"\n{'='*60}")
        print("🔍 Preview режим - разделяне на audio/video на тракове")
        print(f"{'='*60}")
        print(f"Вход: {self.input_file}")
        print(f"Type: {'Video' if self.is_video else 'Audio'}")
        print(f"Изходен формат: .{self.output_format}")
        print(f"Name pattern: {self.name_pattern}")  # НОВО!
        print(f"{'='*60}\n")

        silences = self.detect_silence()

        if not silences:
            print("⚠ Не е открита тишина. Опитай да промениш прага или продължителността.")
            print("\nSuggestions:")
            print(f"  • Увеличи прага (текущ: {self.silence_threshold}dB)")
            print(f"  • Намали продължителността (текуща: {self.silence_duration}s)")
            return

        print("\n📊 Открити периоди на тишина:\n")
        for i, (start, end) in enumerate(silences, 1):
            duration = end - start
            print(f"  Тишина {i:02d}: {self.format_time(start)} → {self.format_time(end)} (продължителност: {self.format_time(duration)})")

        segments = self.calculate_segments(silences)

        if not segments:
            print("\n⚠ No valid segments found (all segments too short).")
            return

        print(f"\n📋 Preview на {len(segments)} трака, които ще бъдат създадени:\n")

        total_duration = 0
        total_tracks = len(segments)

        for i, (start, end) in enumerate(segments, 1):
            duration = end - start
            total_duration += duration
            output_file = self.generate_filename(i, total_tracks)  # НОВО!

            print(f"  Track {i:02d}: {self.format_time(start)} → {self.format_time(end)} "
                  f"(продължителност: {self.format_time(duration)}) → {output_file}")

        print(f"\n{'='*60}")
        print("📊 Statistics:")
        print(f"  Общо тракове: {len(segments)}")
        print(f"  Обща продължителност на съдържанието: {self.format_time(total_duration)}")
        print(f"  Продължителност на файла: {self.format_time(self.get_duration())}")
        print(f"  Продължителност на тишината: {self.format_time(self.get_duration() - total_duration)}")
        print(f"{'='*60}\n")

        print("💡 За реално извличане стартирай без --preview")

    def split(self):
        """Основна функция за разделяне"""
        print(f"\n{'='*60}")
        print("🎵 Audio/Video Track Splitter")
        print(f"{'='*60}")
        print(f"Вход: {self.input_file}")
        print(f"Type: {'Video' if self.is_video else 'Audio'}")
        print(f"Изходен формат: .{self.output_format}")
        print(f"Name pattern: {self.name_pattern}")  # НОВО!
        print(f"Изходна директория: {self.output_dir}/")
        print(f"{'='*60}\n")

        silences = self.detect_silence()

        if not silences:
            print("⚠ Не е открита тишина. Опитай да промениш прага или продължителността.")
            return

        segments = self.calculate_segments(silences)

        if not segments:
            print("⚠ No valid segments found.")
            return

        print(f"\n📦 Извличам {len(segments)} трака...\n")

        success_count = 0
        total_tracks = len(segments)

        for i, (start, end) in enumerate(segments, 1):
            filename = self.generate_filename(i, total_tracks)  # НОВО!
            output_file = self.output_dir / filename

            if self.extract_segment(start, end, output_file, i):
                success_count += 1

        print(f"\n{'='*60}")
        print(f"✅ Успешно извлечени {success_count}/{len(segments)} трака")
        print(f"📁 Изходна директория: {self.output_dir}/")
        print(f"{'='*60}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Разделя audio/video файл на тракове според засечена тишина',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примери:
  # Preview режим
  %(prog)s input.mp3 --preview

  # Основна употреба с имена по подразбиране (track_01, track_02, ...)
  %(prog)s input.mp3

  # Custom naming with wildcards
  %(prog)s input.mp3 -n "Song {num}"
  %(prog)s input.mp3 -n "{name}_{num}"
  %(prog)s input.mp3 -n "Part {n} of {t}"

  # Advanced examples
  %(prog)s input.mp3 -t -40 -d 2.0 -n "Track {num}" -f m4a -b 256k
  %(prog)s concert.mp4 -f mp4 -n "Concert Part {num}"

Naming placeholders:
  {num} or {n}    - Track number (auto-padded: 01, 02, ..., 10, 11, ...)
  {total} или {t} - Общ брой тракове
  {name}          - Оригинално име на файла (без разширение)
        '''
    )

    parser.add_argument('input', help='Входен audio/video файл')
    parser.add_argument('-t', '--threshold', type=float, default=-50,
                       help='Праг за тишина в dB (по подразбиране: -50)')
    parser.add_argument('-d', '--duration', type=float, default=1.0,
                       help='Минимална продължителност на тишината в секунди (по подразбиране: 1.0)')
    parser.add_argument('-f', '--format', default='mp3',
                       help='Изходен формат: mp3, m4a, wav, flac, mp4, mkv (по подразбиране: mp3)')
    parser.add_argument('-b', '--bitrate', default='192k',
                       help='Audio bitrate (по подразбиране: 192k)')
    parser.add_argument('-n', '--name', dest='name_pattern', default='track_{num}',
                       help='Шаблон за изходни имена (по подразбиране: track_{num}). '
                            'Use {num}, {total}, {name} as placeholders')
    parser.add_argument('--video-codec', default='copy',
                       help='Video codec за video output (по подразбиране: copy)')
    parser.add_argument('--audio-codec', default='libmp3lame',
                       help='Audio codec (по подразбиране: libmp3lame за MP3)')
    parser.add_argument('--preview', action='store_true',
                       help='Preview режим: показва какви тракове ще се създадат, без извличане')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ Грешка: файлът '{args.input}' не е намерен!")
        sys.exit(1)

    codec_map = {
        'mp3': 'libmp3lame',
        'm4a': 'aac',
        'wav': 'pcm_s16le',
        'flac': 'flac',
        'opus': 'libopus',
        'ogg': 'libvorbis'
    }

    audio_codec = codec_map.get(args.format, args.audio_codec)

    splitter = SilenceSplitter(
        input_file=args.input,
        silence_threshold=args.threshold,
        silence_duration=args.duration,
        output_format=args.format,
        audio_bitrate=args.bitrate,
        video_codec=args.video_codec,
        audio_codec=audio_codec,
        name_pattern=args.name_pattern  # НОВО!
    )

    if args.preview:
        splitter.preview()
    else:
        splitter.split()


if __name__ == "__main__":
    main()
