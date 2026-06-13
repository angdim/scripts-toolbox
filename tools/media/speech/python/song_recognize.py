#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
Автоматично разпознава аудио файлове чрез Shazam API и ги копира с разпознати имена.
Оригиналните файлове остават непроменени.
"""

import asyncio
import sys
import os
from pathlib import Path
import shutil
import re
from shazamio import Shazam

# Поддържани аудио формати
AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.opus', '.aac', '.wma',
                    '.MP3', '.M4A', '.WAV', '.FLAC', '.OGG', '.OPUS', '.AAC', '.WMA'}

class MusicRecognizer:
    def __init__(self, input_dir, output_dir=None, keep_numbers=True,
                 copy_mode=True, max_retries=3, delay=1.0):
        """
        Args:
            input_dir: Директория със входни файлове
            output_dir: Директория за изход (ако None, създава '_recognized' папка)
            keep_numbers: Запазва ли номерацията в началото (Track 01 -> 01 - Song Name)
            copy_mode: True = копира, False = премества файловете
            max_retries: Максимален брой опити при грешка
            delay: Пауза между заявки в секунди
        """
        self.input_dir = Path(input_dir)
        self.keep_numbers = keep_numbers
        self.copy_mode = copy_mode
        self.max_retries = max_retries
        self.delay = delay

        # Определяне на output директория
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.input_dir.parent / f"{self.input_dir.name}_recognized"

        self.output_dir.mkdir(exist_ok=True)

        # Статистика
        self.total = 0
        self.recognized = 0
        self.failed = 0

    def sanitize_filename(self, filename):
        """Почиства име на файл от невалидни символи"""
        # Премахване на невалидни символи за файлови системи
        invalid_chars = r'[<>:"/\\|?*]'
        cleaned = re.sub(invalid_chars, '', filename)

        # Премахване на множество spaces
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Trim whitespace
        cleaned = cleaned.strip()

        # Ограничаване на дължина (макс 200 символа за безопасност)
        if len(cleaned) > 200:
            cleaned = cleaned[:200]

        return cleaned

    def extract_track_number(self, filename):
        """
        Извлича номер на трак от името на файл.
        Примери: 'track_01.mp3' -> '01', '03 - Song.mp3' -> '03'
        """
        # Търси числа в началото на файла
        match = re.match(r'^(\d+)', filename)
        if match:
            return match.group(1)

        # Търси след underscore или тире
        match = re.search(r'[_\-\s](\d+)', filename)
        if match:
            return match.group(1)

        return None

    async def recognize_file(self, file_path):
        """
        Разпознава един аудио файл чрез Shazam.
        Връща: (title, artist) или (None, None) при неуспех
        """
        shazam = Shazam()

        for attempt in range(self.max_retries):
            try:
                print(f"    🔍 Recognizing... (attempt {attempt + 1}/{self.max_retries})")

                result = await shazam.recognize(str(file_path))

                if 'track' in result:
                    track = result['track']
                    title = track.get('title', 'Unknown Title')
                    artist = track.get('subtitle', 'Unknown Artist')

                    # Допълнителна информация (ако е налична)
                    album = track.get('sections', [{}])[0].get('metadata', [{}])
                    album_name = None

                    for item in album:
                        if item.get('title') == 'Album':
                            album_name = item.get('text')
                            break

                    return title, artist, album_name
                else:
                    print("    ⚠ No match found")
                    return None, None, None

            except Exception as e:
                print(f"    ⚠ Error on attempt {attempt + 1}: {e}")

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.delay * (attempt + 1))  # Increasing delay
                else:
                    return None, None, None

        return None, None, None

    def generate_new_filename(self, original_file, title, artist):
        """
        Генерира ново име на файл според разпознатата информация.

        Формат: [номер - ]Artist - Title.ext
        """
        extension = original_file.suffix

        # Извличане на номер (ако има)
        track_num = self.extract_track_number(original_file.stem)

        # Почистване на имена
        clean_title = self.sanitize_filename(title)
        clean_artist = self.sanitize_filename(artist)

        # Генериране на име
        if self.keep_numbers and track_num:
            new_name = f"{track_num} - {clean_artist} - {clean_title}{extension}"
        else:
            new_name = f"{clean_artist} - {clean_title}{extension}"

        return new_name

    async def process_file(self, file_path):
        """Обработва един файл"""
        print(f"\n{'='*60}")
        print(f"📄 Processing: {file_path.name}")

        # Разпознаване
        title, artist, album = await self.recognize_file(file_path)

        if title and artist:
            # Генериране на ново име
            new_filename = self.generate_new_filename(file_path, title, artist)
            output_path = self.output_dir / new_filename

            # Проверка за съществуващ файл
            counter = 1
            while output_path.exists():
                stem = output_path.stem
                ext = output_path.suffix
                output_path = self.output_dir / f"{stem}_{counter}{ext}"
                counter += 1

            # Копиране или преместване
            try:
                if self.copy_mode:
                    shutil.copy2(file_path, output_path)
                    action = "Copied"
                else:
                    shutil.move(str(file_path), output_path)
                    action = "Moved"

                print(f"  ✅ {action} to: {output_path.name}")
                if album:
                    print(f"     Album: {album}")

                self.recognized += 1
                return True

            except Exception as e:
                print(f"  ❌ Неуспешно {action.lower()}: {e}")
                self.failed += 1
                return False

        else:
            print("  ❌ Could not recognize this file")
            self.failed += 1
            return False

    async def process_directory(self):
        """Обработва всички файлове в директорията"""
        # Намиране на аудио файлове
        audio_files = sorted([
            f for f in self.input_dir.iterdir()
            if f.is_file() and f.suffix in AUDIO_EXTENSIONS
        ])

        if not audio_files:
            print(f"\n❌ No audio files found in {self.input_dir}")
            return

        self.total = len(audio_files)

        print(f"\n{'='*60}")
        print("🎵 Music File Recognizer")
        print(f"{'='*60}")
        print(f"Входна директория:  {self.input_dir}")
        print(f"Изходна директория: {self.output_dir}")
        print(f"Mode: {'Copy' if self.copy_mode else 'Move'}")
        print(f"Запазване на track номера: {self.keep_numbers}")
        print(f"Total files: {self.total}")
        print(f"{'='*60}")

        # Обработка на всеки файл
        for i, file_path in enumerate(audio_files, 1):
            print(f"\n[{i}/{self.total}]", end=" ")
            await self.process_file(file_path)

            # Пауза между заявки
            if i < self.total:
                await asyncio.sleep(self.delay)

        # Финално резюме
        self.print_summary()

    def print_summary(self):
        """Показва финално резюме"""
        print(f"\n{'='*60}")
        print("📊 SUMMARY")
        print(f"{'='*60}")
        print(f"  Total files:      {self.total}")
        print(f"  ✅ Recognized:     {self.recognized}")
        print(f"  ❌ Неуспешни:      {self.failed}")

        if self.recognized > 0:
            success_rate = (self.recognized / self.total) * 100
            print(f"  Success rate:     {success_rate:.1f}%")

        print(f"{'='*60}")
        print(f"\n📁 Изходна директория: {self.output_dir}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Автоматично разпознава музикални файлове и ги копира/преименува',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примери:
  # Recognize files in current directory
  %(prog)s .

  # Recognize files in specific directory
  %(prog)s /path/to/music/folder

  # Specify output directory
  %(prog)s ./tracks -o ./recognized_tracks

  # Преместване на файловете вместо копиране
  %(prog)s ./tracks --move

  # Без запазване на track номерата
  %(prog)s ./tracks --no-numbers

  # Custom delay between requests (in seconds)
  %(prog)s ./tracks --delay 2.0
        '''
    )

    parser.add_argument('input_dir',
                       help='Директория с аудио файлове за разпознаване')
    parser.add_argument('-o', '--output', dest='output_dir',
                       help='Изходна директория (по подразбиране: <input_dir>_recognized)')
    parser.add_argument('--move', action='store_true',
                       help='Премества файловете вместо да ги копира (по подразбиране: copy)')
    parser.add_argument('--no-numbers', action='store_true',
                       help='Не запазва track номерата в изходните имена')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Пауза между API заявките в секунди (по подразбиране: 1.0)')
    parser.add_argument('--retries', type=int, default=3,
                       help='Максимален брой повторни опити за файл (по подразбиране: 3)')

    args = parser.parse_args()

    # Проверка дали директорията съществува
    if not os.path.exists(args.input_dir):
        print(f"❌ Грешка: директорията '{args.input_dir}' не е намерена!")
        sys.exit(1)

    if not os.path.isdir(args.input_dir):
        print(f"❌ Грешка: '{args.input_dir}' не е директория!")
        sys.exit(1)

    # Създаване и стартиране на recognizer
    recognizer = MusicRecognizer(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        keep_numbers=not args.no_numbers,
        copy_mode=not args.move,
        max_retries=args.retries,
        delay=args.delay
    )

    await recognizer.process_directory()


if __name__ == "__main__":
    asyncio.run(main())
