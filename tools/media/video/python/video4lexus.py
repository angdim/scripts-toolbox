#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
Конвертира видео към формат и ограничения, подходящи за Lexus infotainment системи.
"""

import subprocess
import json
from pathlib import Path

# Поддържани формати
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4v',
                   '.MP4', '.AVI', '.MKV', '.MOV', '.WMV', '.FLV', '.M4V'}

# Максимални размери за Lexus RX 450h 2017
MAX_WIDTH = 720
MAX_HEIGHT = 480

def get_video_info(video_path):
    """Извлича информация за видеото (резолюция, fps, audio sample rate)"""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
        
        info = {
            'width': int(video_stream.get('width', 0)) if video_stream else 0,
            'height': int(video_stream.get('height', 0)) if video_stream else 0,
            'fps': eval(video_stream.get('r_frame_rate', '30/1')) if video_stream else 30,
            'sample_rate': int(audio_stream.get('sample_rate', 44100)) if audio_stream else 44100
        }
        return info
    except Exception as e:
        print(f"Warning: Could not read video info: {e}")
        return None

def needs_scaling(width, height):
    """Проверява дали видеото надвишава максималните размери"""
    return width > MAX_WIDTH or height > MAX_HEIGHT

def convert_video(video_file, output_file, video_info):
    """Конвертира видео файл за Lexus съвместимост"""
    
    # Базова FFmpeg команда
    cmd = [
        'ffmpeg',
        '-i', str(video_file),
        '-c:v', 'libx264',
        '-profile:v', 'baseline',
        '-level', '3.1'
    ]
    
    # Добавяме scale филтър само ако е необходимо
    if video_info and needs_scaling(video_info['width'], video_info['height']):
        scale_filter = f"scale='min({MAX_WIDTH},iw)':'min({MAX_HEIGHT},ih)':force_original_aspect_ratio=decrease"
        cmd.extend(['-vf', scale_filter])
        print(f"  → Scaling from {video_info['width']}x{video_info['height']} to max {MAX_WIDTH}x{MAX_HEIGHT}")
    elif video_info:
        print(f"  → Keeping original size: {video_info['width']}x{video_info['height']}")
    
    # Добавяме останалите параметри
    cmd.extend([
        '-b:v', '1500k',
        '-maxrate', '2000k',
        '-bufsize', '4000k',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        '-loglevel', 'error',
        '-stats',
        str(output_file)
    ])
    
    # Показваме запазените параметри
    if video_info:
        print(f"  → FPS: {video_info['fps']:.2f}, Audio: {video_info['sample_rate']}Hz")
    
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0

def main():
    # Създаване на изходна директория
    output_dir = Path('lexus_converted')
    output_dir.mkdir(exist_ok=True)
    
    # Намиране на всички видео файлове
    video_files = [f for f in Path('.').iterdir() 
                   if f.is_file() and f.suffix in VIDEO_EXTENSIONS]
    
    total = len(video_files)
    success = 0
    failed = 0
    
    print("\n\033[93m╔════════════════════════════════════════════════════╗\033[0m")
    print("\033[93m║  Lexus RX 450h Video Converter (Smart Scaling)    ║\033[0m")
    print("\033[93m╚════════════════════════════════════════════════════╝\033[0m")
    print(f"\nFound {total} video file(s)\n")
    
    for i, video_file in enumerate(video_files, 1):
        output_file = output_dir / f"{video_file.stem}_lexus.mp4"
        
        print(f"\033[96m[{i}/{total}] Converting: {video_file.name}\033[0m")
        
        # Анализиране на видеото
        video_info = get_video_info(video_file)
        
        # Конвертиране
        if convert_video(video_file, output_file, video_info):
            # Проверка на размера на изходния файл
            input_size = video_file.stat().st_size / (1024 * 1024)  # MB
            output_size = output_file.stat().st_size / (1024 * 1024)  # MB
            
            print(f"\033[92m✓ Успешно конвертирано: {video_file.name}\033[0m")
            print(f"  Size: {input_size:.1f}MB → {output_size:.1f}MB")
            
            # Предупреждение ако файлът е над 2GB
            if output_size > 2000:
                print("\033[91m  ⚠ WARNING: File exceeds 2GB FAT32 limit!\033[0m")
            
            print()
            success += 1
        else:
            print(f"\033[91m✗ Неуспешно конвертиране: {video_file.name}\033[0m\n")
            failed += 1
    
    # Резюме
    print("\n" + "="*60)
    print("\033[93mConversion Summary:\033[0m")
    print(f"\033[92m  ✓ Successful: {success}\033[0m")
    print(f"\033[91m  ✗ Неуспешни: {failed}\033[0m")
    print(f"\033[93m  Total: {total}\033[0m")
    print("="*60)
    print(f"\nConverted files are in: \033[92m{output_dir}/\033[0m")
    print("\n\033[93mNext steps:\033[0m")
    print("  1. Copy files to FAT32-formatted USB drive")
    print("  2. Keep files under 2GB each")
    print("  3. Test playback with car in Park (P) mode\n")

if __name__ == "__main__":
    main()
