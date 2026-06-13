#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
Автоматично разделя аудио/видео файл на отделни тракове базирано на паузи/тишина.
Използва FFmpeg за детекция на тишина и разделяне.
Опционално разпознава песните чрез Shazam и ги именува автоматично.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
import re
import asyncio
import shutil

# Проверка дали shazamio е инсталиран
SHAZAM_AVAILABLE = False
try:
    from shazamio import Shazam
    SHAZAM_AVAILABLE = True
except ImportError:
    pass

class SilenceSplitter:
    def __init__(self, input_file,
                 silence_threshold=-50,
                 silence_duration=1.0,
                 output_format='mp3',
                 audio_bitrate='192k',
                 video_codec='copy',
                 audio_codec='libmp3lame',
                 name_pattern='track_{num}',
                 recognize=False,
                 recognition_delay=1.5,
                 max_retries=3):

        self.input_file = Path(input_file)
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.output_format = output_format
        self.audio_bitrate = audio_bitrate
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.name_pattern = name_pattern
        self.recognize = recognize
        self.recognition_delay = recognition_delay
        self.max_retries = max_retries

        self.is_video = self.check_if_video()
        self.output_dir = Path(f"{self.input_file.stem}_tracks")
        self.output_dir.mkdir(exist_ok=True)

        # Статистика за разпознаване
        self.recognized_count = 0
        self.recognition_failed = 0

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
        Генерира име на файл според шаблона - ВИНАГИ с номер в началото.

        Формат: {num} - {pattern}.ext
        """
        padding = len(str(total_tracks))
        track_number = f"{track_num:0{padding}d}"

        # Замяна на placeholders в шаблона
        pattern_part = self.name_pattern
        pattern_part = pattern_part.replace('{num}', track_number)
        pattern_part = pattern_part.replace('{n}', track_number)
        pattern_part = pattern_part.replace('{total}', str(total_tracks))
        pattern_part = pattern_part.replace('{t}', str(total_tracks))
        pattern_part = pattern_part.replace('{name}', self.input_file.stem)

        # ВИНАГИ започва с номер, след това шаблона
        # Ако шаблонът вече започва с номер, не го дублираме
        if pattern_part.startswith(track_number):
            filename = pattern_part
        else:
            filename = f"{track_number} - {pattern_part}"

        return f"{filename}.{self.output_format}"

    def sanitize_filename(self, filename):
        """Почиства име на файл от невалидни символи"""
        invalid_chars = r'[<>:"/\\|?*]'
        cleaned = re.sub(invalid_chars, '', filename)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()

        if len(cleaned) > 200:
            cleaned = cleaned[:200]

        return cleaned

    async def recognize_track(self, file_path):
        """
        Разпознава трак чрез Shazam API.
        Връща: (title, artist) или (None, None)
        """
        if not SHAZAM_AVAILABLE:
            return None, None

        shazam = Shazam()

        for attempt in range(self.max_retries):
            try:
                print(f"      🔍 Recognizing via Shazam (attempt {attempt + 1}/{self.max_retries})...")

                result = await shazam.recognize(str(file_path))

                if 'track' in result:
                    track = result['track']
                    title = track.get('title', 'Unknown')
                    artist = track.get('subtitle', 'Unknown')

                    return title, artist
                else:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.recognition_delay)

            except Exception as e:
                print(f"      ⚠ Recognition error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.recognition_delay * (attempt + 1))

        return None, None

    def generate_recognized_filename(self, track_num, total_tracks, title, artist):
        """
        Генерира име базирано на разпознатата информация.
        ВИНАГИ започва с номер!

        Формат: {num} - {artist} - {title}.ext
        """
        padding = len(str(total_tracks))
        track_number = f"{track_num:0{padding}d}"

        clean_title = self.sanitize_filename(title)
        clean_artist = self.sanitize_filename(artist)

        # ВИНАГИ номер в началото
        return f"{track_number} - {clean_artist} - {clean_title}.{self.output_format}"

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

    async def process_and_recognize(self, temp_file, fallback_file, track_num, total_tracks):
        """
        Разпознава трак и го преименува.

        - Ако е разпознат: {num} - {artist} - {title}.ext
        - Ако НЕ е разпознат: {num} - {pattern}.ext (според шаблона)
        """

        title, artist = await self.recognize_track(temp_file)

        if title and artist:
            # УСПЕШНО разпознаване
            new_filename = self.generate_recognized_filename(track_num, total_tracks, title, artist)
            new_path = self.output_dir / new_filename

            # Проверка за дубликат
            counter = 1
            while new_path.exists():
                stem = new_path.stem
                ext = new_path.suffix
                new_path = self.output_dir / f"{stem}_{counter}{ext}"
                counter += 1

            # Преименуване
            shutil.move(str(temp_file), str(new_path))

            print(f"      ✅ Recognized: {artist} - {title}")
            print(f"      📁 Saved as: {new_path.name}")

            self.recognized_count += 1
            return True
        else:
            # НЕУСПЕШНО разпознаване - използваме шаблона
            # fallback_file вече е генериран с правилния формат (номер в началото)
            shutil.move(str(temp_file), str(fallback_file))

            print("      ❌ Could not recognize")
            print(f"      📁 Saved as: {fallback_file.name} (pattern-based)")

            self.recognition_failed += 1
            return False

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
        print(f"Name pattern: {self.name_pattern}")
        print(f"Recognition: {'Enabled' if self.recognize else 'Disabled'}")
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
            output_file = self.generate_filename(i, total_tracks)

            print(f"  Track {i:02d}: {self.format_time(start)} → {self.format_time(end)} "
                  f"(duration: {self.format_time(duration)})")

            if self.recognize:
                print(f"            → (if recognized) {i:02d} - Artist - Title.{self.output_format}")
                print(f"            → (if not found)  {output_file}")
            else:
                print(f"            → {output_file}")

        print(f"\n{'='*60}")
        print("📊 Statistics:")
        print(f"  Общо тракове: {len(segments)}")
        print(f"  Обща продължителност на съдържанието: {self.format_time(total_duration)}")
        print(f"  Продължителност на файла: {self.format_time(self.get_duration())}")
        print(f"  Продължителност на тишината: {self.format_time(self.get_duration() - total_duration)}")
        print(f"{'='*60}\n")

        if self.recognize:
            print("🎵 Recognition enabled:")
            print("   • Разпознати тракове: {num} - {artist} - {title}.ext")
            print("   • Неразпознати тракове: именуване по шаблон")
            print("   • Всички тракове ще бъдат номерирани от 01, 02, 03, ...")

        print("\n💡 За реално извличане стартирай без --preview")

    async def split_async(self):
        """Асинхронна версия на split за разпознаване"""
        print(f"\n{'='*60}")
        print("🎵 Audio/Video Track Splitter")
        print(f"{'='*60}")
        print(f"Вход: {self.input_file}")
        print(f"Type: {'Video' if self.is_video else 'Audio'}")
        print(f"Изходен формат: .{self.output_format}")
        print(f"Name pattern: {self.name_pattern}")
        print(f"Recognition: {'Enabled ✅' if self.recognize else 'Disabled'}")
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
            print(f"\n[{i}/{total_tracks}]")

            if self.recognize:
                # Временен файл за разпознаване
                temp_filename = f"temp_track_{i:04d}.{self.output_format}"
                temp_file = self.output_dir / temp_filename

                # Fallback име според шаблона (вече с номер в началото!)
                fallback_filename = self.generate_filename(i, total_tracks)
                fallback_file = self.output_dir / fallback_filename

                target_file = temp_file
            else:
                # Директно създаване с финално име (номер в началото)
                final_filename = self.generate_filename(i, total_tracks)
                target_file = self.output_dir / final_filename
                fallback_file = target_file

            # Извличане
            if self.extract_segment(start, end, target_file, i):
                if self.recognize:
                    # Разпознаване и преименуване
                    await self.process_and_recognize(target_file, fallback_file, i, total_tracks)

                    # Пауза между заявки
                    if i < total_tracks:
                        await asyncio.sleep(self.recognition_delay)

                success_count += 1
            else:
                # Ако извличането се провали, изтрий временния файл
                if target_file.exists():
                    target_file.unlink()

        # Финално резюме
        print(f"\n{'='*60}")
        print(f"✅ Успешно извлечени {success_count}/{len(segments)} трака")

        if self.recognize:
            print("\n🎵 Recognition Results:")
            print(f"  ✅ Recognized: {self.recognized_count}")
            print(f"  ❌ Неуспешни: {self.recognition_failed}")
            if success_count > 0:
                rate = (self.recognized_count / success_count) * 100
                print(f"  Success rate: {rate:.1f}%")

        print(f"\n📁 Изходна директория: {self.output_dir}/")
        print(f"{'='*60}\n")

    def split(self):
        """Синхронна версия за обратна съвместимост"""
        asyncio.run(self.split_async())


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Разделя audio/video файл на тракове според тишина, с опционално музикално разпознаване',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примери:
  # Preview режим
  %(prog)s input.mp3 --preview

  # Основна употреба без разпознаване
  %(prog)s input.mp3

  # С автоматично разпознаване
  %(prog)s input.mp3 --recognize

  # Потребителски шаблон за имена (всички тракове започват с номер)
  %(prog)s input.mp3 -n "Song"
  # → Results: 01 - Song.mp3, 02 - Song.mp3, ...
  # → With --recognize: 01 - Artist - Title.mp3 (if found) or 01 - Song.mp3 (if not)

  # Пълен пример с разпознаване
  %(prog)s "album.mp3" -t -40 -d 2.0 --recognize -f m4a -b 256k -n "Track"

Naming behavior:
  WITHOUT --recognize:
    Шаблон "track" → 01 - track.mp3, 02 - track.mp3, ...
    Шаблон "track_{num}" → 01 - track_01.mp3, 02 - track_02.mp3, ...

  WITH --recognize:
    Recognized → 01 - Artist - Title.mp3, 02 - Artist - Title.mp3, ...
    Неразпознато → fallback към шаблона (01 - track.mp3, 02 - track.mp3, ...)

  All files maintain sequential numbering from 01, ensuring proper sort order!

Recognition:
  Install shazamio first: pip install shazamio --break-system-packages
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
    parser.add_argument('-n', '--name', dest='name_pattern', default='track',
                       help='Шаблон за изходни имена (по подразбиране: track). Номерът винаги се добавя в началото.')
    parser.add_argument('--video-codec', default='copy',
                       help='Video codec за video output (по подразбиране: copy)')
    parser.add_argument('--audio-codec', default='libmp3lame',
                       help='Audio codec (по подразбиране: libmp3lame за MP3)')
    parser.add_argument('--recognize', action='store_true',
                       help='Включва автоматично музикално разпознаване чрез Shazam (изисква shazamio)')
    parser.add_argument('--recognition-delay', type=float, default=1.5,
                       help='Пауза между заявките за разпознаване в секунди (по подразбиране: 1.5)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Максимален брой повторни опити за трак (по подразбиране: 3)')
    parser.add_argument('--preview', action='store_true',
                       help='Preview режим: показва какви тракове ще се създадат, без извличане')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ Грешка: файлът '{args.input}' не е намерен!")
        sys.exit(1)

    if args.recognize and not SHAZAM_AVAILABLE:
        print("\n❌ Грешка: --recognize изисква библиотеката shazamio!")
        print("Install it with: pip install shazamio --break-system-packages\n")
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
        name_pattern=args.name_pattern,
        recognize=args.recognize,
        recognition_delay=args.recognition_delay,
        max_retries=args.max_retries
    )

    if args.preview:
        splitter.preview()
    else:
        splitter.split()


if __name__ == "__main__":
    main()
