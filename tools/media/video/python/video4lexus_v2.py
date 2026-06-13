#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
Втора версия на video4lexus конвертор с FFmpeg профил за Lexus infotainment системи.
"""

import subprocess
import json
from pathlib import Path

# Поддържани формати
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4v', '.webm',
                   '.MP4', '.AVI', '.MKV', '.MOV', '.WMV', '.FLV', '.M4V', '.WEBM'}

MAX_WIDTH = 720
MAX_HEIGHT = 480

def get_video_dimensions(video_path):
    """Извлича само ширина и височина"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        stream = data['streams'][0]
        return int(stream['width']), int(stream['height'])
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError, IndexError, ValueError):
        return None, None

def convert_video(video_file, output_file):
    """Конвертира видео файл"""
    
    # Получаване на размери
    width, height = get_video_dimensions(video_file)
    
    cmd = ['ffmpeg', '-i', str(video_file)]
    
    # Проверка дали е нужно мащабиране
    if width and height:
        print(f"  → Original: {width}x{height}")
        
        if width > MAX_WIDTH or height > MAX_HEIGHT:
            # Намираме коя страна е лимитиращата
            ratio_w = MAX_WIDTH / width
            ratio_h = MAX_HEIGHT / height
            ratio = min(ratio_w, ratio_h)
            
            new_w = int(width * ratio)
            new_h = int(height * ratio)
            
            # Закръгляме до четни числа (изискване на H.264)
            new_w = new_w - (new_w % 2)
            new_h = new_h - (new_h % 2)
            
            print(f"  → Scaling to: {new_w}x{new_h}")
            cmd.extend(['-vf', f'scale={new_w}:{new_h}'])
        else:
            print("  → No scaling needed")
    
    # Добавяне на кодеци и параметри
    cmd.extend([
        '-c:v', 'libx264',
        '-profile:v', 'baseline',
        '-level', '3.1',
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
    result = subprocess.run(cmd)
    return result.returncode == 0

def main():
    output_dir = Path('lexus_converted')
    output_dir.mkdir(exist_ok=True)
    
    video_files = [f for f in Path('.').iterdir() 
                   if f.is_file() and f.suffix in VIDEO_EXTENSIONS]
    
    total = len(video_files)
    success = 0
    failed = 0
    
    print("\n╔════════════════════════════════════════════════════╗")
    print("║  Lexus RX 450h Video Converter (Smart Scaling)     ║")
    print("╚════════════════════════════════════════════════════╝\n")
    print(f"Found {total} video file(s)\n")
    
    for i, video_file in enumerate(video_files, 1):
        output_file = output_dir / f"{video_file.stem}.mp4"
        
        print(f"[{i}/{total}] Converting: {video_file.name}")
        
        if convert_video(video_file, output_file):
            input_size = video_file.stat().st_size / (1024 * 1024)
            output_size = output_file.stat().st_size / (1024 * 1024)
            
            print(f"✓ Success! {input_size:.1f}MB → {output_size:.1f}MB\n")
            success += 1
        else:
            print("✗ Неуспешно!\n")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {success} successful, {failed} failed, {total} total")
    print("="*60)
    print("\nИзходна папка: lexus_converted/\n")

if __name__ == "__main__":
    main()
