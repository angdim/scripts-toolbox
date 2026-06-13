"""
Помощен скрипт за preview/преглед на конфигурация и междинни резултати при split/fade/concat workflow.
"""

import subprocess
import os
from utils import time_to_seconds, get_font_path


def build_filter_complex(video_path, segments, fade_duration):
    inputs = []
    filters = []
    concat_segments = []
    font = get_font_path()

    for i, (start_time, end_time) in enumerate(segments):
        start = time_to_seconds(start_time)
        end = time_to_seconds(end_time)
        duration = end - start

        inputs.extend(["-i", video_path])

        # Escape на двоеточията за drawtext
        start_esc = start_time.replace(":", "\\:")
        end_esc = end_time.replace(":", "\\:")

        vf = f"[{i}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS"
        vf += f",fade=t=in:st=0:d={fade_duration}"
        if i < len(segments) - 1:
            vf += f",fade=t=out:st={duration - fade_duration}:d={fade_duration}"

        # Статичен текст с оригиналния диапазон на сегмента (горе вляво)
        vf += (
            f",drawtext=fontfile='{font}'"
            f":text='{start_esc} → {end_esc}'"
            f":fontcolor=yellow:fontsize=20"
            f":x=10:y=10"
            f":box=1:boxcolor=black@0.5:boxborderw=4"
        )

        # Вървящ таймер от 0 (долу в средата)
        vf += (
            f",drawtext=fontfile='{font}'"
            f":text='%{{pts\\:hms}}'"
            f":fontcolor=white:fontsize=24"
            f":x=(w-tw)/2:y=h-th-10"
            f":box=1:boxcolor=black@0.4:boxborderw=4"
        )

        vf += f"[v{i}]"
        filters.append(vf)

        af = f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS"
        af += f",afade=t=in:st=0:d={fade_duration}"
        if i < len(segments) - 1:
            af += f",afade=t=out:st={duration - fade_duration}:d={fade_duration}"
        af += f"[a{i}]"
        filters.append(af)

        concat_segments.append(f"[v{i}][a{i}]")

    n = len(segments)
    concat_str = "".join(concat_segments)
    filters.append(f"{concat_str}concat=n={n}:v=1:a=1[outv][outa]")

    filter_complex = ";".join(filters)
    return inputs, filter_complex


def render_preview(video_path, segments, fade_duration, output_path):
    inputs, filter_complex = build_filter_complex(video_path, segments, fade_duration)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "utvideo",
        "-c:a", "pcm_s16le",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        fallback_path = output_path.replace(".mkv", "_ffv1.mkv")
        cmd_fallback = [
            "ffmpeg", "-y", "-loglevel", "warning",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "ffv1",
            "-c:a", "pcm_s16le",
            fallback_path
        ]
        result2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result2.returncode != 0:
            raise RuntimeError(f"Preview рендеринг неуспешен:\n{result2.stderr}")
        return fallback_path

    return output_path


def play_preview(preview_path):
    cmd = [
        "ffplay",
        "-loglevel", "error",
        "-autoexit",
        "-window_title", f"PREVIEW — {os.path.basename(preview_path)}",
        preview_path
    ]
    subprocess.run(cmd)


def preview_video(video_name, settings, preview_dir="preview"):
    os.makedirs(preview_dir, exist_ok=True)

    video_path = f"videos/{video_name}"
    segments = settings["segments"]
    fade_duration = settings["fade"]

    base_name = os.path.splitext(video_name)[0]
    preview_path = os.path.join(preview_dir, f"preview_{base_name}.mkv")

    total_duration = sum(
        time_to_seconds(end) - time_to_seconds(start)
        for start, end in segments
    )

    print(f"\n{'='*55}")
    print(f"  Видео    : {video_name}")
    print(f"  Сегменти : {len(segments)}")
    print(f"  Продължителност на preview : {total_duration:.1f}s")
    print(f"  Fade     : {fade_duration}s")
    print(f"{'='*55}")
    print("  Рендериране (lossless, бързо)...")

    try:
        actual_path = render_preview(video_path, segments, fade_duration, preview_path)
        print(f"  Preview готов: {actual_path}")
        print("  Стартиране на плейър...")
        play_preview(actual_path)
    except RuntimeError as e:
        print(f"  Грешка: {e}")
        return False

    return True


def preview_all_videos(videos_config):
    videos = list(videos_config.items())

    print("\nРежим на преглед:")
    print("  [1] Всички видеа едно след друго")
    print("  [2] Избор на конкретно видео")

    choice = input("\nИзбор (1/2): ").strip()

    if choice == "2":
        for i, (name, _) in enumerate(videos):
            print(f"  [{i+1}] {name}")
        try:
            idx = int(input("Видео номер: ").strip()) - 1
            if 0 <= idx < len(videos):
                videos = [videos[idx]]
            else:
                print("Невалиден избор.")
                return
        except ValueError:
            print("Невалиден вход.")
            return

    for i, (video_name, settings) in enumerate(videos):
        success = preview_video(video_name, settings)

        if not success:
            print(f"  Пропускане на {video_name}.")

        if i < len(videos) - 1:
            answer = input("\nСледващо видео? (y/n): ").strip().lower()
            if answer != "y":
                print("Прегледът е прекратен.")
                return

    print("\nПрегледът е завършен.")
