#!/usr/bin/env python3
"""
Автоматично разделя аудио/видео файл на отделни тракове базирано на паузи/тишина.
Използва FFmpeg за детекция на тишина и разделяне.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
import re

class SilenceSplitter:
    def __init__(self, input_file,
                 silence_threshold=-50,      # dB под който се счита за тишина
                 silence_duration=1.0,       # минимална продължителност на тишината в секунди
                 output_format='mp3',        # mp3, m4a, wav, mp4, mkv и т.н.
                 audio_bitrate='192k',
                 video_codec='copy',
                 audio_codec='libmp3lame'):

        self.input_file = Path(input_file)
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.output_format = output_format
        self.audio_bitrate = audio_bitrate
        self.video_codec = video_codec
        self.audio_codec = audio_codec

        # Автоматично определяне дали входът е видео или аудио
        self.is_video = self.check_if_video()

        # Директория за изход
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
        except:
            return False

    def detect_silence(self):
        """
        Детектира паузи/тишина във файла и връща списък с времена.
        Връща: [(start1, end1), (start2, end2), ...]
        """
        print(f"🔍 Detecting silence (threshold: {self.silence_threshold}dB, min duration: {self.silence_duration}s)...")

        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-af', f'silencedetect=noise={self.silence_threshold}dB:d={self.silence_duration}',
            '-f', 'null',
            '-'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)
        output = result.stdout

        # Парсване на резултата
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

        # Комбиниране на start и end
        silences = list(zip(silence_starts, silence_ends))

        print(f"✓ Found {len(silences)} silence periods")
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
        except:
            return None

    def calculate_segments(self, silences):
        """
        Изчислява сегментите (траковете) базирано на тишината.
        Връща: [(start1, end1), (start2, end2), ...]
        """
        duration = self.get_duration()

        if not duration:
            print("⚠ Could not determine file duration")
            return []

        segments = []

        # Първи сегмент (от началото до първата пауза)
        if silences:
            segments.append((0, silences[0][0]))

        # Средни сегменти (между паузите)
        for i in range(len(silences) - 1):
            start = silences[i][1]  # края на текущата пауза
            end = silences[i + 1][0]  # началото на следващата пауза
            segments.append((start, end))

        # Последен сегмент (от последната пауза до края)
        if silences:
            segments.append((silences[-1][1], duration))

        # Филтриране на твърде къси сегменти (под 3 секунди)
        segments = [(s, e) for s, e in segments if (e - s) >= 3.0]

        print(f"✓ Calculated {len(segments)} track segments")
        return segments

    def extract_segment(self, start, end, output_file, track_num):
        """Извлича един сегмент от файла"""
        duration = end - start

        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-ss', str(start),
            '-t', str(duration),
            '-y'  # Overwrite without asking
        ]

        # Настройки според типа изход
        if self.is_video and self.output_format in ['mp4', 'mkv', 'avi', 'mov']:
            # Видео изход
            cmd.extend([
                '-c:v', self.video_codec,
                '-c:a', self.audio_codec,
                '-b:a', self.audio_bitrate
            ])
        else:
            # Аудио изход
            cmd.extend([
                '-vn',  # Без видео
                '-c:a', self.audio_codec,
                '-b:a', self.audio_bitrate
            ])

        cmd.append(str(output_file))

        print(f"  ⏩ Extracting track {track_num}: {self.format_time(start)} → {self.format_time(end)} ({self.format_time(duration)})")

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

    def split(self):
        """Основна функция за разделяне"""
        print(f"\n{'='*60}")
        print(f"🎵 Audio/Video Track Splitter")
        print(f"{'='*60}")
        print(f"Input: {self.input_file}")
        print(f"Type: {'Video' if self.is_video else 'Audio'}")
        print(f"Output format: .{self.output_format}")
        print(f"Output directory: {self.output_dir}/")
        print(f"{'='*60}\n")

        # 1. Детектиране на тишина
        silences = self.detect_silence()

        if not silences:
            print("⚠ No silence detected. Try adjusting threshold or duration.")
            return

        # 2. Изчисляване на сегменти
        segments = self.calculate_segments(silences)

        if not segments:
            print("⚠ No valid segments found.")
            return

        # 3. Извличане на сегменти
        print(f"\n📦 Extracting {len(segments)} tracks...\n")

        success_count = 0

        for i, (start, end) in enumerate(segments, 1):
            output_file = self.output_dir / f"track_{i:02d}.{self.output_format}"

            if self.extract_segment(start, end, output_file, i):
                success_count += 1

        # 4. Резюме
        print(f"\n{'='*60}")
        print(f"✅ Successfully extracted {success_count}/{len(segments)} tracks")
        print(f"📁 Output directory: {self.output_dir}/")
        print(f"{'='*60}\n")

    def preview(self):
        """Показва само какви тракове ще се създадат"""
        silences = self.detect_silence()
        segments = self.calculate_segments(silences)

        print(f"\n📋 Preview of {len(segments)} tracks:\n")

        for i, (start, end) in enumerate(segments, 1):
            duration = end - start
            print(f"  Track {i:02d}: {self.format_time(start)} → {self.format_time(end)} (duration: {self.format_time(duration)})")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Split audio/video file into tracks based on silence',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage (MP3 output)
  %(prog)s input.mp3

  # Custom silence threshold and duration
  %(prog)s input.mp3 -t -40 -d 2.0

  # Output as M4A with higher bitrate
  %(prog)s input.mp3 -f m4a -b 256k

  # Keep video, extract as MP4
  %(prog)s input.mp4 -f mp4

  # Extract only audio from video as WAV
  %(prog)s input.mp4 -f wav
        '''
    )

    parser.add_argument('input', help='Input audio/video file')
    parser.add_argument('-t', '--threshold', type=float, default=-50,
                       help='Silence threshold in dB (default: -50)')
    parser.add_argument('-d', '--duration', type=float, default=1.0,
                       help='Minimum silence duration in seconds (default: 1.0)')
    parser.add_argument('-f', '--format', default='mp3',
                       help='Output format: mp3, m4a, wav, flac, mp4, mkv (default: mp3)')
    parser.add_argument('-b', '--bitrate', default='192k',
                       help='Audio bitrate (default: 192k)')
    parser.add_argument('--video-codec', default='copy',
                       help='Video codec for video output (default: copy)')
    parser.add_argument('--audio-codec', default='libmp3lame',
                       help='Audio codec (default: libmp3lame for MP3)')
    parser.add_argument('--preview', action='store_true',
                       help='Preview mode - show what tracks will be created without extracting')

    args = parser.parse_args()

    # Валидация на input файл
    if not os.path.exists(args.input):
        print(f"❌ Error: File '{args.input}' not found!")
        sys.exit(1)

    # Автоматично определяне на audio codec според формата
    codec_map = {
        'mp3': 'libmp3lame',
        'm4a': 'aac',
        'wav': 'pcm_s16le',
        'flac': 'flac',
        'opus': 'libopus',
        'ogg': 'libvorbis'
    }

    audio_codec = codec_map.get(args.format, args.audio_codec)

    # Създаване и стартиране на splitter
    splitter = SilenceSplitter(
        input_file=args.input,
        silence_threshold=args.threshold,
        silence_duration=args.duration,
        output_format=args.format,
        audio_bitrate=args.bitrate,
        video_codec=args.video_codec,
        audio_codec=audio_codec
    )

    # Избор между preview и split
    if args.preview:
        splitter.preview()
    else:
        splitter.split()


if __name__ == "__main__":
    main()
