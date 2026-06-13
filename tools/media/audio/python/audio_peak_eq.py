#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
audio_peak_eq.py

Инструмент за Linux за channel balance, peak-базирано усилване и EQ обработка чрез FFmpeg филтри.

Скриптът обработва аудио файлове директно, а при видео файлове променя само
аудио потока и копира видео потока без прекодиране. Когато са заявени channel
balance, EQ и peak нормализация, редът е: първо изравняване на каналите, после
EQ, след това финално измерване на peak и прилагане на gain. Финалната peak
нормализация е последна, защото и balance, и EQ могат да променят максималния
пик на аудио потока.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Sequence


# EQ preset-ите са FFmpeg аудио филтърни фрагменти. По-късно се съединяват
# със запетая, затова всеки елемент трябва да бъде валиден самостоятелен
# FFmpeg аудио филтър.
PRESET_DESCRIPTIONS = {
    "air_boost": "Добавя въздух и отвореност във високите честоти; внимателно при шумни записи.",
    "bass_boost": "Умерено усилва ниските честоти за по-плътен бас.",
    "bass_tighten": "Стяга баса чрез лек low-cut, удар около 90 Hz и намаляване на мътност около 250 Hz.",
    "boomy_bass_reduce": "Намалява бумтене и прекомерен нисък бас.",
    "boxiness_reduce": "Намалява кутиест/стаен характер около ниските среди.",
    "car_audio_clarity": "Оптимизира за слушане в кола: по-малко бумтене и повече яснота.",
    "dark_recording_brighten": "Осветлява тъмни записи чрез присъствие и високи честоти.",
    "de_mud": "Намалява мътност в ниските среди.",
    "harshness_reduce": "Омекотява остър и уморяващ звук в зоната 2.5-4 kHz.",
    "laptop_speakers": "Подготвя звук за малки говорители без реален sub bass.",
    "mains_hum_50hz": "Премахва 50 Hz мрежово бучене и няколко хармоника с по-слаба корекция.",
    "mains_hum_50hz_light": "По-лек вариант срещу 50 Hz мрежово бучене с по-малък риск от артефакти.",
    "music_smile_curve": "Потребителски smile EQ: повече бас и високи, леко прибрани среди.",
    "nasal_reduce": "Намалява носов характер около 900-1300 Hz.",
    "noisy_speech_denoise": "Почиства шумен говор с high/low-pass филтри, FFT шумопотискане и леко усилена разбираемост.",
    "old_record_restoration": "По-силна реставрация за стари записи с ограничена лента и шум.",
    "podcast_voice": "Подобрява говор за подкаст: low-cut, по-малко мътност и повече разбираемост.",
    "presence_boost": "Усилва присъствието, за да изпъкнат вокали/говор/детайли.",
    "rumble_removal": "Премахва нискочестотен rumble от микрофон, транспорт или стая.",
    "sibilance_soften": "Омекотява сибиланти и остри 'с/ш' честоти; не е динамичен de-esser.",
    "soft_loudness_balance": "Лека широколентова тонална корекция чрез firequalizer за по-балансирано слушане.",
    "speech_cleanup": "Базово почистване на говор: low-cut, по-малко мътност, повече яснота.",
    "sub_bass_cleanup": "Премахва излишен sub bass под полезния музикален диапазон.",
    "telephone_voice": "Създава телефонен/радио ефект с ограничена честотна лента.",
    "thin_recording_fuller": "Добавя тяло към тънки записи и леко прибира остротата.",
    "treble_boost": "Умерено усилва високите честоти за повече блясък и детайл.",
    "vinyl_soft_restore": "Лека реставрация за винил/стари записи с умерено шумопотискане.",
    "vocal_clarity": "Подобрява яснота на вокали чрез low-cut, намалена мътност и presence boost.",
    "voice_bright_female": "Стартова точка за по-ясен женски глас с умерено изсветляване.",
    "voice_deep_male": "Стартова точка за дълбок мъжки глас с тяло, но без прекомерна мътност.",
    "warmth": "Добавя топлина в ниските среди и леко прибира високите.",
}

PRESETS = {
    # Добавя въздух и отвореност във високите честоти; внимателно при шумни записи.
    "air_boost": [
        "equalizer=f=10000:t=q:w=0.8:g=2",
        "equalizer=f=14000:t=q:w=0.8:g=1.5",
    ],
    # Умерено усилва ниските честоти за по-плътен бас.
    "bass_boost": [
        "equalizer=f=80:t=q:w=1.0:g=4",
        "equalizer=f=160:t=q:w=1.0:g=2",
    ],
    # Стяга баса: премахва sub rumble, добавя удар и намалява мътност.
    "bass_tighten": [
        "highpass=f=35",
        "equalizer=f=90:t=q:w=1.0:g=2",
        "equalizer=f=250:t=q:w=1.1:g=-2",
    ],
    # Намалява бумтене и прекомерен нисък бас.
    "boomy_bass_reduce": [
        "equalizer=f=80:t=q:w=1.0:g=-3",
        "equalizer=f=150:t=q:w=1.0:g=-2",
    ],
    # Намалява кутиест/стаен характер около ниските среди.
    "boxiness_reduce": [
        "equalizer=f=400:t=q:w=1.2:g=-3",
        "equalizer=f=700:t=q:w=1.0:g=-1.5",
    ],
    # Оптимизира за слушане в кола: по-малко бумтене и повече яснота.
    "car_audio_clarity": [
        "highpass=f=45",
        "equalizer=f=200:t=q:w=1.1:g=-1.5",
        "equalizer=f=2500:t=q:w=1.0:g=1.5",
        "equalizer=f=8000:t=q:w=1.0:g=1",
    ],
    # Осветлява тъмни записи чрез присъствие и високи честоти.
    "dark_recording_brighten": [
        "equalizer=f=3000:t=q:w=1.0:g=1.5",
        "equalizer=f=6000:t=q:w=1.0:g=2",
        "equalizer=f=10000:t=q:w=1.0:g=1.5",
    ],
    # Намалява мътност в ниските среди.
    "de_mud": [
        "equalizer=f=250:t=q:w=1.2:g=-3",
        "equalizer=f=500:t=q:w=1.0:g=-1.5",
    ],
    # Омекотява остър и уморяващ звук в зоната 2.5-4 kHz.
    "harshness_reduce": [
        "equalizer=f=2500:t=q:w=1.2:g=-2",
        "equalizer=f=4000:t=q:w=1.2:g=-2",
    ],
    # Подготвя звук за малки говорители без реален sub bass.
    "laptop_speakers": [
        "highpass=f=120",
        "equalizer=f=250:t=q:w=1.0:g=1",
        "equalizer=f=2500:t=q:w=1.0:g=2",
        "equalizer=f=6000:t=q:w=1.0:g=1.5",
    ],
    # Премахва 50 Hz мрежово бучене и хармоници. Основната честота се реже най-силно.
    "mains_hum_50hz": [
        "equalizer=f=50:t=q:w=15:g=-18",
        "equalizer=f=100:t=q:w=18:g=-10",
        "equalizer=f=150:t=q:w=18:g=-7",
        "equalizer=f=200:t=q:w=18:g=-5",
    ],
    # По-лек вариант срещу 50 Hz мрежово бучене с по-малък риск от артефакти.
    "mains_hum_50hz_light": [
        "equalizer=f=50:t=q:w=15:g=-10",
        "equalizer=f=100:t=q:w=18:g=-5",
        "equalizer=f=150:t=q:w=18:g=-3",
    ],
    # Потребителски smile EQ: повече бас и високи, леко прибрани среди.
    "music_smile_curve": [
        "equalizer=f=80:t=q:w=1.0:g=2",
        "equalizer=f=400:t=q:w=1.2:g=-1.5",
        "equalizer=f=3000:t=q:w=1.0:g=1",
        "equalizer=f=10000:t=q:w=1.0:g=2",
    ],
    # Намалява носов характер около 900-1300 Hz.
    "nasal_reduce": [
        "equalizer=f=900:t=q:w=1.2:g=-2",
        "equalizer=f=1300:t=q:w=1.2:g=-2",
    ],
    # Почиства шумен говор с high/low-pass филтри, FFT шумопотискане и леко усилена разбираемост.
    "noisy_speech_denoise": [
        "highpass=f=90",
        "lowpass=f=10000",
        "afftdn=nf=-28",
        "equalizer=f=3500:t=q:w=1.0:g=2",
    ],
    # По-силна реставрация за стари записи с ограничена лента и шум.
    "old_record_restoration": [
        "highpass=f=70",
        "lowpass=f=12000",
        "equalizer=f=180:t=q:w=1.0:g=-2",
        "equalizer=f=3500:t=q:w=1.0:g=2",
        "afftdn=nf=-25",
    ],
    # Подобрява говор за подкаст: low-cut, по-малко мътност и повече разбираемост.
    "podcast_voice": [
        "highpass=f=90",
        "equalizer=f=180:t=q:w=1.0:g=-2",
        "equalizer=f=3500:t=q:w=1.0:g=3",
        "equalizer=f=8000:t=q:w=1.0:g=-1",
    ],
    # Усилва присъствието, за да изпъкнат вокали/говор/детайли.
    "presence_boost": [
        "equalizer=f=2500:t=q:w=1.0:g=2",
        "equalizer=f=4500:t=q:w=1.0:g=2",
    ],
    # Премахва нискочестотен rumble от микрофон, транспорт или стая.
    "rumble_removal": [
        "highpass=f=60",
    ],
    # Омекотява сибиланти и остри 'с/ш' честоти; не е динамичен de-esser.
    "sibilance_soften": [
        "equalizer=f=6500:t=q:w=1.4:g=-3",
        "equalizer=f=9000:t=q:w=1.2:g=-1.5",
    ],
    # Лека широколентова тонална корекция чрез firequalizer за по-балансирано слушане.
    "soft_loudness_balance": [
        "firequalizer=gain_entry='entry(60,2);entry(120,1.5);entry(1000,0);entry(4500,1.5);entry(10000,1)'",
    ],
    # Базово почистване на говор: low-cut, по-малко мътност, повече яснота.
    "speech_cleanup": [
        "highpass=f=90",
        "equalizer=f=250:t=q:w=1.1:g=-2",
        "equalizer=f=3500:t=q:w=1.0:g=2",
    ],
    # Премахва излишен sub bass под полезния музикален диапазон.
    "sub_bass_cleanup": [
        "highpass=f=35",
    ],
    # Създава телефонен/радио ефект с ограничена честотна лента.
    "telephone_voice": [
        "highpass=f=300",
        "lowpass=f=3400",
        "equalizer=f=1200:t=q:w=1.0:g=2",
    ],
    # Добавя тяло към тънки записи и леко прибира остротата.
    "thin_recording_fuller": [
        "equalizer=f=120:t=q:w=0.9:g=2",
        "equalizer=f=250:t=q:w=1.0:g=1.5",
        "equalizer=f=5000:t=q:w=1.0:g=-1",
    ],
    # Умерено усилва високите честоти за повече блясък и детайл.
    "treble_boost": [
        "equalizer=f=6000:t=q:w=1.0:g=3",
        "equalizer=f=10000:t=q:w=1.0:g=2",
    ],
    # Лека реставрация за винил/стари записи с умерено шумопотискане.
    "vinyl_soft_restore": [
        "highpass=f=45",
        "lowpass=f=15000",
        "equalizer=f=250:t=q:w=1.0:g=-1.5",
        "equalizer=f=3500:t=q:w=1.0:g=1.5",
        "afftdn=nf=-30",
    ],
    # Подобрява яснота на вокали чрез low-cut, намалена мътност и presence boost.
    "vocal_clarity": [
        "highpass=f=80",
        "equalizer=f=250:t=q:w=1.1:g=-2",
        "equalizer=f=3000:t=q:w=1.0:g=3",
        "equalizer=f=5000:t=q:w=1.2:g=1.5",
    ],
    # Стартова точка за по-ясен женски глас с умерено изсветляване.
    "voice_bright_female": [
        "highpass=f=100",
        "equalizer=f=220:t=q:w=1.1:g=-1.5",
        "equalizer=f=4500:t=q:w=1.0:g=2",
        "equalizer=f=9000:t=q:w=1.0:g=1",
    ],
    # Стартова точка за дълбок мъжки глас с тяло, но без прекомерна мътност.
    "voice_deep_male": [
        "highpass=f=70",
        "equalizer=f=120:t=q:w=0.9:g=1.5",
        "equalizer=f=250:t=q:w=1.1:g=-2",
        "equalizer=f=3000:t=q:w=1.0:g=2",
    ],
    # Добавя топлина в ниските среди и леко прибира високите.
    "warmth": [
        "equalizer=f=180:t=q:w=0.9:g=2.5",
        "equalizer=f=400:t=q:w=1.0:g=1",
        "equalizer=f=6000:t=q:w=1.0:g=-1",
    ],
}

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi"}
MAX_SAFE_TARGET_DB = -0.1
DEFAULT_BALANCE_THRESHOLD_DB = 0.25


def parse_arguments() -> argparse.Namespace:
    """Парсира CLI опциите и показва практически примери в --help."""
    parser = argparse.ArgumentParser(
        prog="audio_peak_eq.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        description=(
            "Прилага незадължително channel balance, EQ и peak-базиран gain, така че "
            "максималният audio peak да достигне зададеното target ниво."
        ),
        epilog="""
Примери:
  audio_peak_eq.py -i input.wav -o output.wav -t -0.5
  audio_peak_eq.py -i input.wav -o output.wav -B -t -0.5
  audio_peak_eq.py -i input.mkv -o output.mkv -B --balance-mode all -t -1.0
  audio_peak_eq.py -i input.mp4 -o output.mp4 -p vocal_clarity -t -1.0
  audio_peak_eq.py -i song.flac -o song_eq.flac --preset bass_boost --target-level -0.7
  audio_peak_eq.py -i in.wav -o out.wav --eq-filter "equalizer=f=1000:t=q:w=1:g=2"
  audio_peak_eq.py --list-presets

Препоръчителна последователност:
  1. Channel balance, ако е заявен с -B/--balance-channels.
  2. EQ preset-и и потребителски EQ филтри.
  3. Финална peak нормализация.

  Скриптът следва този ред автоматично. Balance коригира канален imbalance
  на източника, EQ работи върху вече подравнени канали, а peak нормализацията
  е последна, защото предишните два етапа могат да променят максималния peak.
""",
    )
    parser._optionals.title = "Опции"

    parser.add_argument("-h", "--help", action="help", help="Показва това помощно съобщение и излиза.")
    parser.add_argument("-i", "--input", help="Входен audio/video файл.")
    parser.add_argument("-o", "--output", help="Изходен файл.")
    parser.add_argument(
        "-t",
        "--target-level",
        type=float,
        default=-0.5,
        help="Target максимален peak в dBFS, например -0.5. По подразбиране: -0.5",
    )
    parser.add_argument(
        "-p",
        "--preset",
        choices=sorted(PRESETS),
        help="EQ preset, който се прилага след channel balance и преди peak нормализацията.",
    )
    parser.add_argument(
        "-e",
        "--eq-filter",
        action="append",
        default=[],
        help=(
            "Потребителски FFmpeg audio filter. Може да се използва многократно. "
            "Филтрите се добавят след preset филтрите."
        ),
    )
    parser.add_argument(
        "-B",
        "--balance-channels",
        action="store_true",
        help=(
            "Изравнява peak нивата между каналите преди EQ. В stereo режим усилва "
            "по-слабия L/R канал; в all режим усилва всеки по-слаб канал до най-силния."
        ),
    )
    parser.add_argument(
        "--balance-mode",
        choices=("stereo", "all"),
        default="stereo",
        help=(
            "Режим за channel balance: 'stereo' балансира само L/R; 'all' балансира "
            "всички audio канали към най-силния канал. По подразбиране: stereo."
        ),
    )
    parser.add_argument(
        "--balance-threshold",
        type=float,
        default=DEFAULT_BALANCE_THRESHOLD_DB,
        help=(
            "Минимална peak разлика в dB, над която се прилага channel balance. "
            f"По подразбиране: {DEFAULT_BALANCE_THRESHOLD_DB}."
        ),
    )
    parser.add_argument(
        "--analyzer",
        choices=("ffmpeg", "ffmpeg-normalize"),
        default="ffmpeg",
        help="Backend за peak анализ. По подразбиране: ffmpeg volumedetect.",
    )
    parser.add_argument(
        "--audio-codec",
        default="auto",
        help="Изходен audio codec. Използвай 'auto' за избор според разширението. По подразбиране: auto",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        help="Опционален output audio sample rate, например 48000.",
    )
    parser.add_argument(
        "--bitrate",
        help="Опционален output audio bitrate за lossy codecs, например 192k.",
    )
    parser.add_argument(
        "--no-video-copy",
        action="store_true",
        help="Не копирай video streams. Обичайно видеото се копира без промяна.",
    )
    parser.add_argument(
        "--overwrite",
        "-y",
        action="store_true",
        help="Презаписва изходния файл, ако вече съществува.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Запазва временния EQ файл за проверка.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показва FFmpeg командите, без да ги изпълнява.",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Показва наличните EQ preset-и и излиза.",
    )

    args = parser.parse_args()
    if args.list_presets:
        return args
    if args.balance_threshold < 0:
        parser.error("--balance-threshold трябва да бъде >= 0")
    if not args.input or not args.output:
        parser.error("-i/--input и -o/--output са задължителни, освен при --list-presets")
    return args


def run_command(command: Sequence[str], *, dry_run: bool = False, capture: bool = False) -> str:
    """Изпълнява subprocess команда с ясен терминален изход и обработка на грешки."""
    printable = " ".join(shlex_quote(part) for part in command)
    print(f"$ {printable}")
    if dry_run:
        return ""

    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        raise SystemExit(f"Командата завърши с грешка, exit code {exc.returncode}") from exc

    if capture:
        return (result.stdout or "") + (result.stderr or "")
    return ""


def shlex_quote(value: str) -> str:
    """Екранира аргумент на команда за четим dry-run изход."""
    import shlex

    return shlex.quote(str(value))


def require_dependency(name: str) -> None:
    """Спира рано, ако липсва необходима външна команда."""
    if shutil.which(name) is None:
        raise SystemExit(f"Липсваща зависимост: {name}. Инсталирай я и опитай отново.")


def check_dependencies(args: argparse.Namespace) -> None:
    """Проверява външните инструменти, нужни за избрания работен процес."""
    require_dependency("ffmpeg")
    require_dependency("ffprobe")
    if args.analyzer == "ffmpeg-normalize":
        require_dependency("ffmpeg-normalize")


def list_presets() -> None:
    """Показва всички вградени preset-и, описанията им и FFmpeg филтърните вериги."""
    print("Налични EQ preset-и:")
    for name, filters in sorted(PRESETS.items()):
        description = PRESET_DESCRIPTIONS.get(name, "Няма описание.")
        print(f"\n{name}:")
        print(f"  предназначение: {description}")
        print("  филтри:")
        for item in filters:
            print(f"    {item}")


def has_stream(input_path: Path, stream_type: str) -> bool:
    """Връща True, ако ffprobe открие поне един поток от заявения тип."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v" if stream_type == "video" else "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(input_path),
    ]
    output = run_command(command, capture=True)
    return bool(output.strip())


def get_audio_channel_count(input_path: Path) -> int:
    """Връща броя канали в първия audio stream според ffprobe."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=channels",
        "-of",
        "csv=p=0",
        str(input_path),
    ]
    output = run_command(command, capture=True).strip()
    try:
        return int(output.splitlines()[0])
    except (IndexError, ValueError) as exc:
        raise SystemExit(f"Неуспешно извличане на броя audio канали за: {input_path}") from exc


def choose_audio_codec(output_path: Path, requested: str, has_video_stream: bool) -> str:
    """Избира подходящ codec според изходното разширение, освен ако е зададен явно."""
    if requested != "auto":
        return requested

    ext = output_path.suffix.lower()
    if ext == ".wav":
        return "pcm_s16le"
    if ext == ".flac":
        return "flac"
    if ext == ".mp3":
        return "libmp3lame"
    if ext in {".m4a", ".mp4", ".mov"} or has_video_stream:
        return "aac"
    if ext == ".ogg":
        return "libvorbis"
    return "aac"


def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    audio_filters: Iterable[str],
    args: argparse.Namespace,
) -> list[str]:
    """Създава FFmpeg команда, която филтрира аудио и копира видео, когато има такова."""
    filters = [item for item in audio_filters if item]
    has_video_stream = has_stream(input_path, "video")
    codec = choose_audio_codec(output_path, args.audio_codec, has_video_stream)

    command = ["ffmpeg", "-hide_banner", "-y" if args.overwrite else "-n", "-i", str(input_path)]

    if filters:
        command += ["-af", ",".join(filters)]

    if has_video_stream and not args.no_video_copy:
        command += ["-map", "0", "-c:v", "copy", "-c:a", codec, "-c:s", "copy"]
    else:
        command += ["-vn", "-c:a", codec]

    if args.sample_rate:
        command += ["-ar", str(args.sample_rate)]
    if args.bitrate:
        command += ["-b:a", args.bitrate]

    command.append(str(output_path))
    return command


def parse_ffmpeg_max_volume(output: str) -> float:
    """Извлича max_volume от stderr изхода на FFmpeg volumedetect."""
    matches = re.findall(r"max_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB", output)
    if not matches:
        raise SystemExit("Неуспешно извличане на max_volume от FFmpeg volumedetect изхода.")
    value = matches[-1]
    if value == "-inf":
        raise SystemExit("Входът изглежда тих/без сигнал; peak нормализацията няма смисъл.")
    return float(value)


def analyze_peak_ffmpeg(input_path: Path) -> float:
    """Анализира максималния пик чрез FFmpeg volumedetect."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
    output = run_command(command, capture=True)
    return parse_ffmpeg_max_volume(output)


def analyze_peak_ffmpeg_normalize(input_path: Path) -> float:
    """Анализира true peak чрез ffmpeg-normalize, когато JSON статистиката е налична."""
    command = ["ffmpeg-normalize", str(input_path), "-n", "--print-stats"]
    output = run_command(command, capture=True)

    # Различните версии на ffmpeg-normalize форматират изхода различно.
    # Първо търсим JSON ключове, после използваме резервен regex за често срещани peak етикети.
    try:
        first = output.find("[")
        last = output.rfind("]")
        if first != -1 and last != -1:
            data = json.loads(output[first : last + 1])
            if data and "input_tp" in data[0]:
                return float(data[0]["input_tp"])
            if data and "max_volume" in data[0]:
                return float(data[0]["max_volume"])
    except (ValueError, TypeError, KeyError):
        pass

    patterns = [
        r"input_tp['\"]?\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        r"max_volume['\"]?\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        r"true peak[^-\d]*(-?\d+(?:\.\d+)?)\s*dB",
    ]
    for pattern in patterns:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))

    raise SystemExit(
        "Неуспешно извличане на peak от ffmpeg-normalize изхода. "
        "Използвай --analyzer ffmpeg или провери версията на ffmpeg-normalize."
    )


def analyze_peak(input_path: Path, analyzer: str) -> float:
    """Изпраща peak анализа към избрания backend механизъм."""
    if analyzer == "ffmpeg-normalize":
        return analyze_peak_ffmpeg_normalize(input_path)
    return analyze_peak_ffmpeg(input_path)


def analyze_channel_peak(input_path: Path, channel_index: int) -> float:
    """Измерва peak на конкретен канал чрез pan към mono и volumedetect."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-af",
        f"pan=mono|c0=c{channel_index},volumedetect",
        "-f",
        "null",
        "-",
    ]
    output = run_command(command, capture=True)
    return parse_ffmpeg_max_volume(output)


def analyze_channel_peaks(input_path: Path, channel_count: int) -> list[float]:
    """Измерва peak нивото на всеки audio канал поотделно."""
    peaks: list[float] = []
    for channel_index in range(channel_count):
        print(f"Анализирам peak на канал {channel_index + 1}/{channel_count}: {input_path}")
        peaks.append(analyze_channel_peak(input_path, channel_index))
    return peaks


def db_to_linear(gain_db: float) -> float:
    """Преобразува dB gain към линейна стойност за FFmpeg pan expressions."""
    return 10 ** (gain_db / 20)


def build_channel_balance_filter(
    peaks: Sequence[float],
    threshold: float,
    mode: str,
) -> str | None:
    """Създава pan filter, който усилва по-слабите канали до най-силния channel peak."""
    channel_count = len(peaks)
    if channel_count < 2:
        print("Channel balance се пропуска: audio stream-ът е mono.")
        return None

    if mode == "stereo" and channel_count != 2:
        print(
            "Channel balance се пропуска: stereo режимът изисква точно 2 канала. "
            f"Открити канали: {channel_count}. Използвай --balance-mode all за multi-channel."
        )
        return None

    strongest_peak = max(peaks)
    gains_db = [strongest_peak - peak for peak in peaks]
    if all(gain <= threshold for gain in gains_db):
        print(
            "Channel balance не е нужен: максималната разлика между каналите е "
            f"{max(gains_db):.2f} dB при праг {threshold:.2f} dB."
        )
        return None

    if strongest_peak > -1.0:
        print(
            "Предупреждение: най-силният канал е близо до 0 dBFS; "
            "финалната peak нормализация остава задължителна последна стъпка."
        )

    channel_layout = "stereo" if channel_count == 2 else f"{channel_count}c"
    expressions = []
    for index, gain_db in enumerate(gains_db):
        linear = db_to_linear(gain_db) if gain_db > threshold else 1.0
        expressions.append(f"c{index}={linear:.9g}*c{index}")

    print("Channel peak нива:")
    for index, peak in enumerate(peaks):
        print(f"  канал {index + 1}: {peak:.2f} dBFS, gain {gains_db[index]:+.2f} dB")

    return f"pan={channel_layout}|" + "|".join(expressions)


def build_channel_balance_filter_for_file(input_path: Path, args: argparse.Namespace) -> str | None:
    """Анализира входа и връща pan filter за channel balance, ако е необходим."""
    channel_count = get_audio_channel_count(input_path)
    peaks = analyze_channel_peaks(input_path, channel_count)
    return build_channel_balance_filter(peaks, args.balance_threshold, args.balance_mode)


def collect_eq_filters(args: argparse.Namespace) -> list[str]:
    """Създава финалния списък EQ филтри от preset и потребителски филтри."""
    filters: list[str] = []
    if args.preset:
        filters.extend(PRESETS[args.preset])
    filters.extend(args.eq_filter or [])
    return filters


def collect_pre_normalization_filters(
    input_path: Path,
    args: argparse.Namespace,
    eq_filters: Sequence[str],
) -> list[str]:
    """Създава filter chain за етапа преди финалната peak нормализация: balance -> EQ."""
    filters: list[str] = []
    if args.balance_channels:
        if args.dry_run:
            print(
                "Dry run: channel balance анализът се пропуска, защото filter gain-ите "
                "зависят от измерените channel peaks."
            )
        else:
            balance_filter = build_channel_balance_filter_for_file(input_path, args)
            if balance_filter:
                filters.append(balance_filter)

    filters.extend(eq_filters)
    return filters


def warn_about_eq(filters: Sequence[str]) -> None:
    """Предупреждава за EQ усилвания, които могат да вдигнат peak нивото."""
    if not filters:
        return
    joined = ",".join(filters)
    gains = [float(item) for item in re.findall(r"(?:^|:)g=(-?\d+(?:\.\d+)?)", joined)]
    if any(gain > 0 for gain in gains) or "gain_entry" in joined:
        print("Предупреждение: EQ съдържа усилвания; peak ще се анализира след EQ, за да се избегне clipping.")


def warn_about_target(target_level: float) -> None:
    """Предупреждава, когато target е твърде близо до цифровия максимум."""
    if target_level > 0:
        raise SystemExit("Target нивото трябва да бъде <= 0 dBFS, за да не се предизвиква clipping.")
    if target_level > MAX_SAFE_TARGET_DB:
        print("Предупреждение: target е много близо до 0 dBFS; lossy encoding може да създаде inter-sample peaks.")


def apply_eq_filters(
    input_path: Path,
    output_path: Path,
    filters: Sequence[str],
    args: argparse.Namespace,
) -> None:
    """Прилага само EQ/filter етапа към временен или краен изход."""
    command = build_ffmpeg_command(input_path, output_path, filters, args)
    run_command(command, dry_run=args.dry_run)


def apply_peak_normalization(
    input_path: Path,
    output_path: Path,
    target_level: float,
    args: argparse.Namespace,
) -> float:
    """Анализира максималния peak, изчислява gain и го прилага чрез FFmpeg volume филтър."""
    if args.dry_run:
        print("Dry run: peak анализът и финалният gain render се пропускат, защото gain зависи от измереното аудио.")
        return float("nan")

    print(f"Анализирам peak чрез {args.analyzer}: {input_path}")
    detected_peak = analyze_peak(input_path, args.analyzer)
    gain = target_level - detected_peak

    print(f"Открит max peak:  {detected_peak:.2f} dBFS")
    print(f"Target max peak:  {target_level:.2f} dBFS")
    print(f"Необходим gain:   {gain:+.2f} dB")

    if gain > 0 and target_level > -1.0:
        print("Предупреждение: положителен gain близо до 0 dBFS може да clip-не след lossy encoding.")

    gain_filter = f"volume={gain:.6f}dB"
    command = build_ffmpeg_command(input_path, output_path, [gain_filter], args)
    run_command(command, dry_run=args.dry_run)
    return gain


def validate_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Проверява входния и изходния път преди началото на обработката."""
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    if not input_path.is_file():
        raise SystemExit(f"Входният файл не съществува: {input_path}")
    if input_path.suffix.lower() not in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS:
        print(f"Предупреждение: непознато разширение '{input_path.suffix}'; опитвам FFmpeg обработка въпреки това.")
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"Изходният файл съществува: {output_path}. Използвай --overwrite за презапис.")
    if input_path == output_path:
        raise SystemExit("Входният и изходният път трябва да са различни.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return input_path, output_path


def main() -> int:
    """Координира parser-а, balance/EQ етапа, peak анализа и финалното рендериране."""
    args = parse_arguments()
    if args.list_presets:
        list_presets()
        return 0

    check_dependencies(args)
    warn_about_target(args.target_level)
    input_path, output_path = validate_paths(args)
    eq_filters = collect_eq_filters(args)
    warn_about_eq(eq_filters)

    if not has_stream(input_path, "audio"):
        raise SystemExit(f"Не е открит audio stream във входа: {input_path}")

    pre_filters = collect_pre_normalization_filters(input_path, args, eq_filters)

    if not pre_filters:
        if args.balance_channels:
            print("Не е приложен channel balance и не е избран EQ; прилагам само peak нормализация.")
        else:
            print("Не е избран EQ/channel balance; прилагам само peak нормализация.")
        apply_peak_normalization(input_path, output_path, args.target_level, args)
        print("Готово.")
        return 0

    print("Ред на обработка: channel balance -> EQ -> peak нормализация.")
    with tempfile.TemporaryDirectory(prefix="audio_peak_eq_") as temp_dir:
        temp_suffix = output_path.suffix if has_stream(input_path, "video") else ".wav"
        temp_path = Path(temp_dir) / f"pre_normalize_stage{temp_suffix}"
        stage_args = argparse.Namespace(**vars(args))
        stage_args.overwrite = True

        print(f"Временен pre-normalization файл: {temp_path}")
        apply_eq_filters(input_path, temp_path, pre_filters, stage_args)
        apply_peak_normalization(temp_path, output_path, args.target_level, args)

        if args.keep_temp and not args.dry_run:
            kept_path = output_path.with_name(f"{output_path.stem}.pre_normalize_stage{output_path.suffix}")
            shutil.copy2(temp_path, kept_path)
            print(f"Запазен pre-normalization stage файл: {kept_path}")

    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
