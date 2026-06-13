"""
Помощен модул за FFmpeg обработката при split/fade/concat project workflow.
"""

import subprocess
import os
from utils import time_to_seconds

def generate_ffmpeg_fade_chain(video_path, segments, fade_duration):
    inputs = []
    filters = []
    concat_segments = []

    for i, (start_time, end_time) in enumerate(segments):
        start = time_to_seconds(start_time)
        end = time_to_seconds(end_time)
        duration = end - start

        inputs.extend(["-i", video_path])

        # Видео филтър за сегмента
        vf = f"[{i}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS"
        vf += f",fade=t=in:st=0:d={fade_duration}"
        if i < len(segments) - 1:
            vf += f",fade=t=out:st={duration - fade_duration}:d={fade_duration}"
        vf += f"[v{i}]"
        filters.append(vf)

        # Аудио филтър за сегмента
        af = f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS"
        af += f",afade=t=in:st=0:d={fade_duration}"
        if i < len(segments) - 1:
            af += f",afade=t=out:st={duration - fade_duration}:d={fade_duration}"
        af += f"[a{i}]"
        filters.append(af)

        concat_segments.append(f"[v{i}][a{i}]")

    # Единен concat с v=1:a=1 — правилният начин
    n = len(segments)
    concat_str = "".join(concat_segments)
    filters.append(f"{concat_str}concat=n={n}:v=1:a=1[outv][outa]")

    filter_complex = ";".join(filters)
    return inputs, filter_complex


def process_video(video_path, segments, fade_duration, encoding_params, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"processed_{os.path.basename(video_path)}")

    inputs, filter_complex = generate_ffmpeg_fade_chain(video_path, segments, fade_duration)

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",   # Отделни -map за видео...
        "-map", "[outa]",   # ...и аудио
        "-c:v", encoding_params["video"]["codec"],
        "-crf", str(encoding_params["video"]["crf"]),
        "-preset", encoding_params["video"]["preset"],
        *(["-profile:v", encoding_params["video"]["profile"]] if "profile" in encoding_params["video"] else []),
        *(["-tune", encoding_params["video"]["tune"]] if "tune" in encoding_params["video"] else []),
        "-c:a", encoding_params["audio"]["codec"],
        "-b:a", encoding_params["audio"]["bitrate"],
        *(["-ac", str(encoding_params["audio"]["channels"])] if "channels" in encoding_params["audio"] else []),
        *(["-ar", encoding_params["audio"]["sample_rate"]] if "sample_rate" in encoding_params["audio"] else []),
        "-movflags", "+faststart",
        output_file
    ]

    print("FFmpeg команда:")
    print(" ".join(cmd))

    try:
        subprocess.run(cmd, check=True)
        print(f"Успешно обработен файл: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Грешка при обработка на {video_path}: {str(e)}")
        raise


def process_all_videos(videos_config, encoding_params):
    for video, settings in videos_config.items():
        process_video(
            video_path=f"videos/{video}",
            segments=settings["segments"],
            fade_duration=settings["fade"],
            encoding_params=encoding_params
        )
