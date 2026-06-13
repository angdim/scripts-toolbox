#!/usr/bin/env python3
# scripts-toolbox: entrypoint

"""
Трета версия на video4lexus конвертор с допълнителни проверки и автоматични корекции.
"""

# Актуализиран Python скрипт с автоматична корекция

import subprocess
import json
from pathlib import Path
from fractions import Fraction

# Поддържани формати
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4v', '.webm',
                   '.MP4', '.AVI', '.MKV', '.MOV', '.WMV', '.FLV', '.M4V', '.WEBM'}

# Максимални размери за Lexus RX 450h 2017
MAX_WIDTH = 720
MAX_HEIGHT = 480

def get_video_info(video_path):
    """Извлича детайлна информация за видеото"""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-show_format',
        str(video_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)

        if not video_stream:
            return None

        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))

        # Изчисляване на aspect ratio
        dar = video_stream.get('display_aspect_ratio', f"{width}:{height}")

        # Парсване на DAR
        try:
            dar_parts = dar.split(':')
            dar_fraction = Fraction(int(dar_parts[0]), int(dar_parts[1]))
        except (ValueError, ZeroDivisionError):
            dar_fraction = Fraction(width, height)

        # FPS
        fps_str = video_stream.get('r_frame_rate', '30/1')
        try:
            fps_parts = fps_str.split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1])
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        info = {
            'width': width,
            'height': height,
            'dar': dar_fraction,
            'dar_decimal': float(dar_fraction),
            'fps': fps,
            'sample_rate': int(audio_stream.get('sample_rate', 44100)) if audio_stream else 44100,
            'duration': float(data['format'].get('duration', 0))
        }

        return info
    except Exception as e:
        print(f"  \033[91mГрешка при четене на video info: {e}\033[0m")
        return None

def calculate_encoding_strategy(video_info):
    """
    Определя оптималната стратегия за кодиране въз основа на aspect ratio

    Връща: (strategy, width, height, description)
    """

    if not video_info:
        return ('simple', 640, 480, 'Default fallback')

    width = video_info['width']
    height = video_info['height']
    dar = video_info['dar_decimal']

    # Проверка дали е вече правилен размер
    if width <= MAX_WIDTH and height <= MAX_HEIGHT:
        return ('keep', width, height, f'Already optimal ({width}x{height})')

    # Определяме дали е широкоекранно (16:9, 16:10, 2.35:1 и т.н.)
    is_widescreen = dar >= 1.6  # 16:9 = 1.777, 16:10 = 1.6

    if is_widescreen:
        # За широкоекранно видео използваме анаморфен метод
        # Мащабираме до 640x480 (което ще бъде разтегнато до 720x480)
        # Това запазва оригиналния 16:9 aspect ratio

        # Изчисляваме височината за 640 ширина запазвайки aspect ratio
        target_height = int(640 / dar)

        # Закръгляме до четно число
        target_height = target_height - (target_height % 2)

        # Ако височината надвишава 480, коригираме
        if target_height > 480:
            target_height = 480
            target_width = int(480 * dar)
            target_width = target_width - (target_width % 2)
        else:
            target_width = 640

        return ('anamorphic', target_width, target_height,
                f'Anamorphic {target_width}x{target_height} → 720x480 (preserves 16:9)')

    else:
        # За 4:3 или близки формати - директно мащабиране
        # Изчисляваме размерите запазвайки aspect ratio

        ratio_w = MAX_WIDTH / width
        ratio_h = MAX_HEIGHT / height
        ratio = min(ratio_w, ratio_h)

        new_w = int(width * ratio)
        new_h = int(height * ratio)

        # Закръгляме до четни числа
        new_w = new_w - (new_w % 2)
        new_h = new_h - (new_h % 2)

        return ('direct', new_w, new_h,
                f'Direct scale to {new_w}x{new_h}')

def convert_video(video_file, output_file, video_info):
    """Конвертира видео файл с интелигентна стратегия"""

    strategy, target_w, target_h, description = calculate_encoding_strategy(video_info)

    print(f"  → Strategy: {description}")
    if video_info:
        print(f"  → Original: {video_info['width']}x{video_info['height']} "
              f"(DAR {video_info['dar_decimal']:.2f}:1, {video_info['fps']:.2f}fps)")

    # Базова FFmpeg команда
    cmd = [
        'ffmpeg',
        '-i', str(video_file),
        '-c:v', 'libx264',
        '-profile:v', 'baseline',
        '-level', '3.1'
    ]

    # Избор на филтър според стратегията
    if strategy == 'keep':
        # Запазваме оригиналния размер
        cmd.extend(['-vf', 'setsar=1:1'])

    elif strategy == 'anamorphic':
        # Анаморфен метод - мащабираме до целевия размер
        vf = f"scale={target_w}:{target_h}:flags=lanczos,setsar=1:1"
        cmd.extend(['-vf', vf])
        # Добавяме aspect ratio метадата (за плеъри които я уважават)
        cmd.extend(['-aspect', '16:9'])

    elif strategy == 'direct':
        # Директно мащабиране
        vf = f"scale={target_w}:{target_h}:flags=lanczos,setsar=1:1"
        cmd.extend(['-vf', vf])

    else:  # 'simple' fallback
        vf = "scale=640:480:flags=lanczos,setsar=1:1"
        cmd.extend(['-vf', vf])

    # Останалите параметри
    cmd.extend([
        '-b:v', '1500k',
        '-maxrate', '2000k',
        '-bufsize', '4000k',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        '-y',
        str(output_file)
    ])

    print("  → Processing...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        error_msg = result.stderr
        print("\033[91m  FFmpeg грешка:\033[0m")
        # Показваме последните няколко реда от грешката
        error_lines = error_msg.strip().split('\n')
        for line in error_lines[-5:]:
            print(f"    {line}")

    return result.returncode == 0

def format_duration(seconds):
    """Форматира времетраене в читаем формат"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def main():
    # Създаване на изходна директория
    output_dir = Path('lexus_converted')
    output_dir.mkdir(exist_ok=True)

    # Намиране на всички видео файлове
    video_files = [f for f in Path('.').iterdir()
                   if f.is_file() and f.suffix in VIDEO_EXTENSIONS]

    if not video_files:
        print("\n\033[91mNo video files found in current directory!\033[0m\n")
        return

    total = len(video_files)
    success = 0
    failed = 0
    total_input_size = 0
    total_output_size = 0

    print("\n\033[93m╔════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[93m║  Lexus RX 450h Video Converter (Intelligent Anamorphic)    ║\033[0m")
    print("\033[93m╚════════════════════════════════════════════════════════════╝\033[0m")
    print(f"\n\033[96mFound {total} video file(s)\033[0m\n")

    for i, video_file in enumerate(video_files, 1):
        output_file = output_dir / f"{video_file.stem}.mp4"

        print(f"\033[96m{'='*60}\033[0m")
        print(f"\033[96m[{i}/{total}] {video_file.name}\033[0m")
        print(f"\033[96m{'='*60}\033[0m")

        # Анализиране на видеото
        video_info = get_video_info(video_file)

        # Конвертиране
        if convert_video(video_file, output_file, video_info):
            # Статистика
            input_size = video_file.stat().st_size / (1024 * 1024)
            output_size = output_file.stat().st_size / (1024 * 1024)

            total_input_size += input_size
            total_output_size += output_size

            compression_ratio = ((input_size - output_size) / input_size * 100) if input_size > 0 else 0

            print("\033[92m✓ SUCCESS!\033[0m")
            print(f"  Вход:  {input_size:.1f} MB")
            print(f"  Изход: {output_size:.1f} MB ({compression_ratio:+.1f}%)")

            if video_info and video_info['duration'] > 0:
                print(f"  Продължителност: {format_duration(video_info['duration'])}")

            # Предупреждения
            if output_size > 2000:
                print("\033[91m  ⚠ WARNING: File exceeds 2GB FAT32 limit!\033[0m")

            print()
            success += 1
        else:
            print("\033[91m✗ FAILED!\033[0m\n")
            failed += 1

    # Финално резюме
    print(f"\n\033[93m{'='*60}\033[0m")
    print("\033[93m║  CONVERSION SUMMARY\033[0m")
    print(f"\033[93m{'='*60}\033[0m")
    print(f"\033[92m  ✓ Successful: {success}\033[0m")
    print(f"\033[91m  ✗ Неуспешни:  {failed}\033[0m")
    print(f"\033[93m  Total:        {total}\033[0m")
    print(f"\033[93m{'='*60}\033[0m")
    print(f"  Общ входен размер:  {total_input_size:.1f} MB")
    print(f"  Общ изходен размер: {total_output_size:.1f} MB")

    if total_input_size > 0:
        overall_ratio = ((total_input_size - total_output_size) / total_input_size * 100)
        print(f"  Overall Change:    {overall_ratio:+.1f}%")

    print(f"\033[93m{'='*60}\033[0m")
    print(f"\n\033[92mИзходна папка: {output_dir}/\033[0m")
    print("\n\033[93mNext steps:\033[0m")
    print(f"  1. Copy files from '{output_dir}/' to FAT32 USB drive")
    print("  2. Ensure USB drive is formatted as FAT32")
    print("  3. Test playback with car in Park (P) mode")
    print("  4. Провери дали aspect ratio е правилен (без разтягане)\n")

if __name__ == "__main__":
    main()
