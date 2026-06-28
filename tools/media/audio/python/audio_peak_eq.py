#!/usr/bin/env python3
# scripts-toolbox: entrypoint
"""
audio_peak_eq.py

Инструмент за Linux за анализ, channel balance, EQ обработка и нормализация чрез FFmpeg филтри.

Скриптът обработва аудио файлове директно, а при видео файлове променя само
аудио потока и копира видео потока без прекодиране. Когато са заявени channel
balance, EQ и нормализация, редът е: първо изравняване на каналите, после
EQ/почистващи филтри, след това финална peak или loudness нормализация.
Финалната нормализация е последна, защото balance, EQ и denoise могат да
променят peak и възприеманата сила на аудио потока.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Sequence, cast


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
DEFAULT_LOUDNESS_TARGETS = {
    "speech": -16.0,
    "music": -14.0,
    "other": -18.0,
}
DEFAULT_TRUE_PEAK_TARGET_DB = -1.5
DEFAULT_LRA_TARGET = 11.0
DEFAULT_ANALYSIS_SECONDS = 0.0
DEFAULT_SILENCE_THRESHOLD_DB = -45.0
DEFAULT_SILENCE_DURATION = 2.0
DEFAULT_KEEP_SILENCE = 0.4
DEFAULT_SILENCE_WINDOW = 0.02
SPECTRAL_BANDS = {
    "sub": (20, 60, "sub бас / rumble"),
    "bass": (60, 200, "бас"),
    "low_mid": (200, 500, "ниски среди / mud"),
    "mid": (500, 2000, "среди"),
    "presence": (2000, 5000, "presence / разбираемост"),
    "sibilance": (5000, 9000, "сибиланти / острота"),
    "air": (9000, 16000, "въздух / най-високи"),
}


@dataclass
class AudioTechnicalInfo:
    """Технически данни за първия audio stream и контейнера."""

    duration: float | None = None
    codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    bit_rate: int | None = None
    container: str | None = None


@dataclass
class AudioAnalysis:
    """Обобщен резултат от автоматичния анализ."""

    input_file: str
    technical: AudioTechnicalInfo
    max_peak_db: float | None = None
    mean_volume_db: float | None = None
    integrated_lufs: float | None = None
    true_peak_db: float | None = None
    loudness_range_lu: float | None = None
    loudness_threshold_lufs: float | None = None
    silence_ratio: float | None = None
    silence_segments: int = 0
    channel_peaks_db: list[float] = field(default_factory=list)
    spectral_bands_db: dict[str, float] = field(default_factory=dict)
    spectral_relative_db: dict[str, float] = field(default_factory=dict)
    detected_content_type: str = "other"
    content_confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class SilenceSegment:
    """Открит сегмент тишина според silencedetect."""

    start: float
    end: float
    duration: float


@dataclass
class TimeRange:
    """Запазен времеви диапазон от оригиналния файл след премахване на паузи."""

    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class AudioRecommendation:
    """Препоръка за подобрение, изведена от анализа."""

    content_type: str
    confidence: float
    target_lufs: float
    target_true_peak_db: float
    target_lra: float
    preset_names: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    deficits: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalization_mode: str = "loudness"


def parse_arguments() -> argparse.Namespace:
    """Парсира CLI опциите и показва практически примери в --help."""
    parser = argparse.ArgumentParser(
        prog="audio_peak_eq.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        description=(
            "Анализира и подобрява audio/video файлове чрез FFmpeg. Поддържа "
            "диагностика, автоматична препоръка, channel balance, EQ, peak "
            "нормализация и loudness нормализация."
        ),
        epilog="""
Примери:
  audio_peak_eq.py -aa -i input.wav
  audio_peak_eq.py -rp -i input.wav -aj report.json
  audio_peak_eq.py -ap -i input.wav -o improved.wav -ct auto
  audio_peak_eq.py -i input.wav -o output.wav -t -0.5
  audio_peak_eq.py -i input.wav -o output.wav -nm loudness -lt -16 -tp -1.5
  audio_peak_eq.py -i input.wav -o output.wav -B -t -0.5
  audio_peak_eq.py -i input.mkv -o output.mkv -B --balance-mode all -t -1.0
  audio_peak_eq.py -i input.mp4 -o output.mp4 -p vocal_clarity -t -1.0
  audio_peak_eq.py -i song.flac -o song_eq.flac --preset bass_boost --target-level -0.7
  audio_peak_eq.py -i in.wav -o out.wav --eq-filter "equalizer=f=1000:t=q:w=1:g=2"
  audio_peak_eq.py --analyze-silence -i input.wav --silence-threshold -45 --silence-duration 2
  audio_peak_eq.py --trim-silence -i input.wav -o trimmed.wav --keep-silence 0.4 --overwrite
  audio_peak_eq.py --trim-silence -i input.wav -o trimmed.wav --trim-silence-scope edges --keep-start-silence 0.2 --keep-end-silence 0.8
  audio_peak_eq.py --trim-silence -i input.mp4 -o trimmed.mp4 --cut-transition crossfade --video-cut-transition crossfade
  audio_peak_eq.py -lp

Основни режими:
  -aa / --analyze-audio
      Само анализира входа и печата отчет. Не изисква -o/--output.

  -rp / --recommend-processing
      Анализира входа и предлага корекция с FFmpeg филтри. Не обработва файла.

  -ap / --apply-recommendation
      Анализира входа, изгражда препоръчана filter chain и създава изходен файл.
      Изисква -o/--output.

Препоръчителна последователност при обработка:
  1. Channel balance, ако е заявен с -B/--balance-channels.
  2. Автоматично препоръчани филтри, EQ preset-и и потребителски EQ филтри.
  3. Изрязване/скъсяване на дълги паузи, ако е заявено с --trim-silence.
  4. Финална нормализация: peak или loudness според -nm/--normalization-mode.

  Скриптът следва този ред автоматично. Balance коригира канален imbalance
  на източника, EQ/denoise работи върху вече подравнени канали, silence trim
  променя времевата структура, а нормализацията е последна, защото предишните
  етапи могат да променят peak и loudness.

Класификация на съдържанието:
  -ct / --content-type auto|speech|music|other
      auto използва консервативни heuristics по loudness, паузи, честотни ленти
      и канална информация. При ниска увереност препоръките са по-предпазливи.
""",
    )
    parser._optionals.title = "Опции"

    parser.add_argument("-h", "--help", action="help", help="Показва това помощно съобщение и излиза.")
    parser.add_argument("-i", "--input", help="Входен audio/video файл.")
    parser.add_argument("-o", "--output", help="Изходен файл.")
    parser.add_argument(
        "-aa",
        "--analyze-audio",
        action="store_true",
        help="Анализира входния audio stream и извежда диагностичен отчет, без да създава изходен файл.",
    )
    parser.add_argument(
        "-rp",
        "--recommend-processing",
        action="store_true",
        help="Анализира входа и предлага конкретна корекция с preset-и и FFmpeg филтри, без да обработва файла.",
    )
    parser.add_argument(
        "-ap",
        "--apply-recommendation",
        action="store_true",
        help="Прилага автоматично препоръчаната обработка. Изисква -o/--output.",
    )
    parser.add_argument(
        "-aj",
        "--analysis-json",
        help="Записва анализа и препоръката като JSON файл. Полезно за преглед, логове и повторяеми batch процеси.",
    )
    parser.add_argument(
        "-asr",
        "--analyze-silence",
        action="store_true",
        help="Само анализира паузи/тишина чрез silencedetect и извежда сегментите, без да създава изходен файл.",
    )
    parser.add_argument(
        "-ct",
        "--content-type",
        choices=("auto", "speech", "music", "other"),
        default="auto",
        help="Тип съдържание за препоръките. 'auto' опитва автоматично разпознаване. По подразбиране: auto.",
    )
    parser.add_argument(
        "-as",
        "--analysis-seconds",
        type=float,
        default=DEFAULT_ANALYSIS_SECONDS,
        help=(
            "Ограничава част от анализа до първите N секунди. 0 означава целия файл. "
            "При много дълги файлове стойности 120-300 ускоряват диагностиката. По подразбиране: 0."
        ),
    )
    parser.add_argument(
        "-t",
        "--target-level",
        type=float,
        default=-0.5,
        help="Target максимален sample peak в dBFS при -nm peak, например -0.5. По подразбиране: -0.5.",
    )
    parser.add_argument(
        "-nm",
        "--normalization-mode",
        choices=("peak", "loudness"),
        default=None,
        help=(
            "Финална нормализация: 'peak' използва volume gain до --target-level; "
            "'loudness' използва EBU R128 loudnorm. Ако липсва, ръчната обработка използва peak, "
            "а -ap/--apply-recommendation използва loudness."
        ),
    )
    parser.add_argument(
        "-lt",
        "--loudness-target",
        type=float,
        help=(
            "Target integrated loudness в LUFS за -nm loudness. Ако липсва, се избира според типа: "
            "speech -16, music -14, other -18."
        ),
    )
    parser.add_argument(
        "-tp",
        "--true-peak-target",
        type=float,
        default=DEFAULT_TRUE_PEAK_TARGET_DB,
        help=f"Target true peak за loudnorm в dBTP. По подразбиране: {DEFAULT_TRUE_PEAK_TARGET_DB}.",
    )
    parser.add_argument(
        "-lr",
        "--lra-target",
        type=float,
        default=DEFAULT_LRA_TARGET,
        help=f"Target loudness range за loudnorm в LU. По подразбиране: {DEFAULT_LRA_TARGET}.",
    )
    parser.add_argument(
        "-p",
        "--preset",
        choices=sorted(PRESETS),
        help="EQ preset, който се прилага след channel balance и преди финалната нормализация.",
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
        "-bm",
        "--balance-mode",
        choices=("stereo", "all"),
        default="stereo",
        help=(
            "Режим за channel balance: 'stereo' балансира само L/R; 'all' балансира "
            "всички audio канали към най-силния канал. По подразбиране: stereo."
        ),
    )
    parser.add_argument(
        "-bt",
        "--balance-threshold",
        type=float,
        default=DEFAULT_BALANCE_THRESHOLD_DB,
        help=(
            "Минимална peak разлика в dB, над която се прилага channel balance. "
            f"По подразбиране: {DEFAULT_BALANCE_THRESHOLD_DB}."
        ),
    )
    parser.add_argument(
        "-az",
        "--analyzer",
        choices=("ffmpeg", "ffmpeg-normalize"),
        default="ffmpeg",
        help="Backend за peak анализ. По подразбиране: ffmpeg volumedetect.",
    )
    parser.add_argument(
        "-ts",
        "--trim-silence",
        action="store_true",
        help=(
            "Изрязва/скъсява паузи по-дълги от --silence-duration чрез FFmpeg silenceremove. "
            "Прилага се след balance/EQ и преди финалната нормализация."
        ),
    )
    parser.add_argument(
        "-ste",
        "--silence-trim-engine",
        choices=("auto", "silenceremove", "concat"),
        default="auto",
        help=(
            "Механизъм за silence trim. auto използва silenceremove за прост audio trim и concat "
            "при fade/crossfade или видео. concat е нужен за точни transition-и. По подразбиране: auto."
        ),
    )
    parser.add_argument(
        "-st",
        "--silence-threshold",
        type=float,
        default=DEFAULT_SILENCE_THRESHOLD_DB,
        help=f"Праг за тишина в dBFS. По подразбиране: {DEFAULT_SILENCE_THRESHOLD_DB}.",
    )
    parser.add_argument(
        "-sd",
        "--silence-duration",
        type=float,
        default=DEFAULT_SILENCE_DURATION,
        help=f"Минимална продължителност на пауза за обработка в секунди. По подразбиране: {DEFAULT_SILENCE_DURATION}.",
    )
    parser.add_argument(
        "-ks",
        "--keep-silence",
        type=float,
        default=DEFAULT_KEEP_SILENCE,
        help=(
            "Fallback стойност за тишината, която да се запази от обработена пауза, "
            "ако не са зададени специфични --keep-start/--keep-middle/--keep-end параметри. "
            f"По подразбиране: {DEFAULT_KEEP_SILENCE}."
        ),
    )
    parser.add_argument(
        "-tss",
        "--trim-silence-scope",
        choices=("all", "edges", "middle", "start", "end"),
        default="all",
        help=(
            "Кои паузи да се обработват: all=начало+среда+край, edges=само начало+край, "
            "middle=повтарящи се вътрешни паузи, start=само начало, end=само край. "
            "По подразбиране: all."
        ),
    )
    parser.add_argument(
        "-kss",
        "--keep-start-silence",
        type=float,
        help="Тишина в секунди, която да остане от начална пауза. Ако липсва, използва --keep-silence.",
    )
    parser.add_argument(
        "-kms",
        "--keep-middle-silence",
        type=float,
        help="Тишина в секунди, която да остане от вътрешни паузи. Ако липсва, използва --keep-silence.",
    )
    parser.add_argument(
        "-kes",
        "--keep-end-silence",
        type=float,
        help="Тишина в секунди, която да остане от крайна пауза. Ако липсва, използва --keep-silence.",
    )
    parser.add_argument(
        "-sm",
        "--silence-channel-mode",
        choices=("all", "any"),
        default="all",
        help=(
            "Multi-channel режим за тишина. all приема тишина само ако всички канали са под прага; "
            "any е по-агресивен. По подразбиране: all."
        ),
    )
    parser.add_argument(
        "-dm",
        "--silence-detection",
        choices=("avg", "rms", "peak", "median", "ptp", "dev"),
        default="rms",
        help="Метод за оценка на тишината в silenceremove. По подразбиране: rms.",
    )
    parser.add_argument(
        "-sw",
        "--silence-window",
        type=float,
        default=DEFAULT_SILENCE_WINDOW,
        help=f"Времеви прозорец за silence detection в секунди. По подразбиране: {DEFAULT_SILENCE_WINDOW}.",
    )
    parser.add_argument(
        "-ctn",
        "--cut-transition",
        choices=("none", "fade", "crossfade"),
        default="none",
        help=(
            "Audio transition на cut местата при concat trim: none, fade или crossfade. "
            "fade прави fade-out/fade-in; crossfade припокрива съседните сегменти. По подразбиране: none."
        ),
    )
    parser.add_argument(
        "-cfd",
        "--cut-fade-duration",
        type=float,
        default=0.03,
        help="Продължителност на fade/crossfade около cut в секунди. По подразбиране: 0.03.",
    )
    parser.add_argument(
        "-cfc",
        "--cut-fade-curve",
        choices=("tri", "qsin", "hsin", "esin", "log", "exp"),
        default="tri",
        help="Крива за audio fade/crossfade. По подразбиране: tri.",
    )
    parser.add_argument(
        "-vtn",
        "--video-cut-transition",
        choices=("match", "none", "fade", "crossfade"),
        default="match",
        help=(
            "Video transition на cut местата при видео concat trim: match следва --cut-transition, "
            "none изключва video fade, fade прави fade-out/fade-in, crossfade използва FFmpeg xfade. "
            "По подразбиране: match."
        ),
    )
    parser.add_argument(
        "-ac",
        "--audio-codec",
        default="auto",
        help="Изходен audio codec. Използвай 'auto' за избор според разширението. По подразбиране: auto",
    )
    parser.add_argument(
        "-sr",
        "--sample-rate",
        type=int,
        help="Опционален output audio sample rate, например 48000.",
    )
    parser.add_argument(
        "-br",
        "--bitrate",
        help="Опционален output audio bitrate за lossy codecs, например 192k.",
    )
    parser.add_argument(
        "-nv",
        "--no-video-copy",
        action="store_true",
        help="Не копирай video streams. Обичайно видеото се копира без промяна.",
    )
    parser.add_argument(
        "-ow",
        "--overwrite",
        "-y",
        action="store_true",
        help="Презаписва изходния файл, ако вече съществува.",
    )
    parser.add_argument(
        "-kt",
        "--keep-temp",
        action="store_true",
        help="Запазва временния pre-normalization файл за проверка.",
    )
    parser.add_argument(
        "-dr",
        "--dry-run",
        action="store_true",
        help="Показва FFmpeg командите, без да ги изпълнява.",
    )
    parser.add_argument(
        "-lp",
        "--list-presets",
        action="store_true",
        help="Показва наличните EQ preset-и и излиза.",
    )

    args = parser.parse_args()
    if args.list_presets:
        return args
    if args.balance_threshold < 0:
        parser.error("--balance-threshold трябва да бъде >= 0")
    if args.analysis_seconds < 0:
        parser.error("--analysis-seconds трябва да бъде >= 0")
    if args.silence_threshold > 0:
        parser.error("--silence-threshold трябва да бъде <= 0 dBFS")
    if args.silence_duration <= 0:
        parser.error("--silence-duration трябва да бъде > 0")
    if args.keep_silence < 0:
        parser.error("--keep-silence трябва да бъде >= 0")
    for name in ("keep_start_silence", "keep_middle_silence", "keep_end_silence"):
        value = getattr(args, name)
        if value is not None and value < 0:
            parser.error(f"--{name.replace('_', '-')} трябва да бъде >= 0")
    if args.silence_window < 0 or args.silence_window > 10:
        parser.error("--silence-window трябва да бъде между 0 и 10 секунди")
    if args.cut_fade_duration < 0:
        parser.error("--cut-fade-duration трябва да бъде >= 0")
    if args.true_peak_target > 0:
        parser.error("--true-peak-target трябва да бъде <= 0 dBTP")
    if not args.input:
        parser.error("-i/--input е задължителен, освен при --list-presets")
    output_required = not (args.analyze_audio or args.recommend_processing or args.analyze_silence) or args.apply_recommendation
    if output_required and not args.output:
        parser.error("-o/--output е задължителен при обработка и при --apply-recommendation")
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


def get_audio_technical_info(input_path: Path) -> AudioTechnicalInfo:
    """Извлича технически данни за първия audio stream чрез ffprobe JSON."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    output = run_command(command, capture=True)
    try:
        data = cast(dict[str, Any], json.loads(output))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Неуспешно четене на ffprobe JSON за: {input_path}") from exc

    streams = cast(list[dict[str, Any]], data.get("streams", []))
    audio_stream: dict[str, Any] = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        {},
    )
    fmt = cast(dict[str, Any], data.get("format", {}))

    def optional_int(value: object) -> int | None:
        try:
            return int(str(value)) if value not in (None, "N/A") else None
        except (TypeError, ValueError):
            return None

    def optional_float(value: object) -> float | None:
        try:
            return float(str(value)) if value not in (None, "N/A") else None
        except (TypeError, ValueError):
            return None

    return AudioTechnicalInfo(
        duration=optional_float(fmt.get("duration")),
        codec=audio_stream.get("codec_name"),
        sample_rate=optional_int(audio_stream.get("sample_rate")),
        channels=optional_int(audio_stream.get("channels")),
        channel_layout=audio_stream.get("channel_layout"),
        bit_rate=optional_int(audio_stream.get("bit_rate") or fmt.get("bit_rate")),
        container=fmt.get("format_name"),
    )


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


def parse_optional_db(value: str | None) -> float | None:
    """Преобразува FFmpeg numeric dB стойност към float, като пази липсващи/безкрайни стойности."""
    if value is None or value in {"-inf", "inf", "nan", "-nan"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_ffmpeg_volume_stats(output: str) -> dict[str, float | None]:
    """Извлича mean_volume и max_volume от FFmpeg volumedetect изход."""
    mean_matches = re.findall(r"mean_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB", output)
    max_matches = re.findall(r"max_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB", output)
    return {
        "mean_volume_db": parse_optional_db(mean_matches[-1] if mean_matches else None),
        "max_peak_db": parse_optional_db(max_matches[-1] if max_matches else None),
    }


def add_analysis_duration(command: list[str], seconds: float) -> list[str]:
    """Добавя -t към FFmpeg анализа, когато е зададен положителен лимит в секунди."""
    if seconds > 0:
        command.extend(["-t", f"{seconds:g}"])
    return command


def run_audio_filter_analysis(input_path: Path, audio_filter: str, analysis_seconds: float = 0) -> str:
    """Изпълнява FFmpeg анализ върху първия audio stream с даден audio filter."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
    ]
    add_analysis_duration(command, analysis_seconds)
    command += ["-af", audio_filter, "-f", "null", "-"]
    return run_command(command, capture=True)


def analyze_volume_stats(input_path: Path, analysis_seconds: float = 0) -> dict[str, float | None]:
    """Измерва sample peak и mean volume чрез FFmpeg volumedetect."""
    output = run_audio_filter_analysis(input_path, "volumedetect", analysis_seconds)
    return parse_ffmpeg_volume_stats(output)


def extract_last_json_object(output: str) -> dict[str, object] | None:
    """Намира последния JSON обект във FFmpeg изход, използван от loudnorm."""
    matches = re.findall(r"\{(?:.|\n)*?\}", output)
    for item in reversed(matches):
        try:
            return json.loads(item)
        except json.JSONDecodeError:
            continue
    return None


def analyze_loudnorm_stats(
    input_path: Path,
    target_lufs: float,
    true_peak_target: float,
    lra_target: float,
    analysis_seconds: float = 0,
) -> dict[str, float | None]:
    """Измерва EBU R128 loudness, true peak и LRA чрез FFmpeg loudnorm JSON."""
    loudnorm_filter = (
        f"loudnorm=I={target_lufs:g}:TP={true_peak_target:g}:"
        f"LRA={lra_target:g}:print_format=json"
    )
    output = run_audio_filter_analysis(input_path, loudnorm_filter, analysis_seconds)
    data = extract_last_json_object(output) or {}

    def get_float(key: str) -> float | None:
        value = data.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return parse_optional_db(value)
        return None

    return {
        "input_i": get_float("input_i"),
        "input_tp": get_float("input_tp"),
        "input_lra": get_float("input_lra"),
        "input_thresh": get_float("input_thresh"),
        "target_offset": get_float("target_offset"),
    }


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


def analyze_band_mean_volume(
    input_path: Path,
    low_frequency: int,
    high_frequency: int,
    analysis_seconds: float = 0,
) -> float | None:
    """Измерва средното ниво в честотна лента чрез highpass/lowpass и volumedetect."""
    band_filter = f"highpass=f={low_frequency},lowpass=f={high_frequency},volumedetect"
    stats = parse_ffmpeg_volume_stats(run_audio_filter_analysis(input_path, band_filter, analysis_seconds))
    return stats["mean_volume_db"]


def analyze_spectral_bands(input_path: Path, analysis_seconds: float = 0) -> dict[str, float]:
    """Измерва груб спектрален баланс по практически полезни честотни ленти."""
    result: dict[str, float] = {}
    for name, (low_frequency, high_frequency, description) in SPECTRAL_BANDS.items():
        print(f"Анализирам честотна лента {name} ({description}): {low_frequency}-{high_frequency} Hz")
        value = analyze_band_mean_volume(input_path, low_frequency, high_frequency, analysis_seconds)
        if value is not None:
            result[name] = value
    return result


def measured_analysis_duration(duration: float | None, analysis_seconds: float = 0) -> float | None:
    """Връща реалната продължителност, върху която се прави анализ."""

    if analysis_seconds > 0 and duration:
        return min(duration, analysis_seconds)
    return duration


def parse_silencedetect_output(output: str, measured_duration: float | None = None) -> list[SilenceSegment]:
    """Парсва FFmpeg silencedetect stderr и връща silence сегменти."""

    starts = [float(item) for item in re.findall(r"silence_start:\s*([\d.]+)", output)]
    ended_segments = [
        SilenceSegment(
            start=max(0.0, float(end) - float(length)),
            end=float(end),
            duration=float(length),
        )
        for end, length in re.findall(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", output)
    ]

    if measured_duration and len(starts) > len(ended_segments):
        start = starts[-1]
        ended_segments.append(
            SilenceSegment(
                start=start,
                end=measured_duration,
                duration=max(0.0, measured_duration - start),
            )
        )

    return ended_segments


def detect_silence_segments(
    input_path: Path,
    duration: float | None,
    analysis_seconds: float = 0,
    threshold_db: float = -45.0,
    minimum_duration: float = 0.5,
) -> tuple[list[SilenceSegment], float | None]:
    """Открива периоди на тишина и връща сегменти и приблизителен дял от анализа."""
    output = run_audio_filter_analysis(
        input_path,
        f"silencedetect=noise={threshold_db:g}dB:d={minimum_duration:g}",
        analysis_seconds,
    )
    measured_duration = measured_analysis_duration(duration, analysis_seconds)
    segments = parse_silencedetect_output(output, measured_duration)
    if not measured_duration or measured_duration <= 0:
        return segments, None

    total_silence = sum(segment.duration for segment in segments)
    return segments, min(1.0, max(0.0, total_silence / measured_duration))


def print_silence_report(
    input_path: Path,
    segments: Sequence[SilenceSegment],
    silence_ratio: float | None,
    args: argparse.Namespace,
) -> None:
    """Печата подробен отчет за откритите паузи и очакваната обработка."""

    print("\n=== Анализ на тишина/паузи ===")
    print(f"Файл: {input_path}")
    print(f"Праг: {args.silence_threshold:g} dBFS")
    print(f"Минимална продължителност: {args.silence_duration:g} s")
    print(f"Scope: {args.trim_silence_scope}")
    print(
        "Запазвана тишина при trim: "
        f"start={resolve_keep_silence(args, 'start'):g}s, "
        f"middle={resolve_keep_silence(args, 'middle'):g}s, "
        f"end={resolve_keep_silence(args, 'end'):g}s"
    )
    print(f"Канален режим: {args.silence_channel_mode}")
    print(f"Detection: {args.silence_detection}, window={args.silence_window:g} s")
    if silence_ratio is not None:
        print(f"Общо засечена тишина: {silence_ratio * 100:.1f}% от анализирания участък")
    if not segments:
        print("Не са открити паузи над зададения праг.")
        return

    print("Сегменти:")
    for index, segment in enumerate(segments, start=1):
        kept = min(resolve_keep_silence(args, classify_silence_segment_position(segment, segments)), segment.duration)
        removed = max(0.0, segment.duration - kept)
        action = "ще се скъси" if args.trim_silence and removed > 0 else "само отчет"
        print(
            f"  {index:02d}. {segment.start:9.3f}s -> {segment.end:9.3f}s "
            f"({segment.duration:7.3f}s), keep {kept:.3f}s, remove {removed:.3f}s [{action}]"
        )


def classify_silence_segment_position(segment: SilenceSegment, segments: Sequence[SilenceSegment]) -> str:
    """Класифицира silence сегмент като start/middle/end за отчетните keep стойности."""

    if segments and segment is segments[0] and segment.start <= 0.05:
        return "start"
    if segments and segment is segments[-1]:
        return "end"
    return "middle"


def should_trim_silence_position(position: str, scope: str) -> bool:
    """Проверява дали даден тип pause segment се обработва според избрания scope."""

    return scope == "all" or scope == position or (scope == "edges" and position in {"start", "end"})


def build_removed_silence_ranges(
    segments: Sequence[SilenceSegment],
    args: argparse.Namespace,
) -> list[TimeRange]:
    """Преобразува silence сегменти в диапазони, които трябва да бъдат изрязани."""

    removed: list[TimeRange] = []
    for segment in segments:
        position = classify_silence_segment_position(segment, segments)
        if not should_trim_silence_position(position, args.trim_silence_scope):
            continue

        keep = min(resolve_keep_silence(args, position), segment.duration)
        if keep >= segment.duration:
            continue

        if position == "start":
            start = segment.start
            end = segment.end - keep
        elif position == "end":
            start = segment.start + keep
            end = segment.end
        else:
            left_keep = keep / 2
            right_keep = keep - left_keep
            start = segment.start + left_keep
            end = segment.end - right_keep

        if end > start:
            removed.append(TimeRange(start=start, end=end))

    return removed


def build_kept_time_ranges(duration: float, removed_ranges: Sequence[TimeRange]) -> list[TimeRange]:
    """Връща комплемента на removed ranges като запазени time ranges."""

    kept: list[TimeRange] = []
    cursor = 0.0
    for removed in sorted(removed_ranges, key=lambda item: item.start):
        start = max(0.0, min(duration, removed.start))
        end = max(0.0, min(duration, removed.end))
        if start > cursor:
            kept.append(TimeRange(cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        kept.append(TimeRange(cursor, duration))
    return [item for item in kept if item.duration > 0.001]


def resolve_silence_trim_engine(args: argparse.Namespace, input_path: Path) -> str:
    """Избира silenceremove или concat engine според опциите и типа вход."""

    if not args.trim_silence:
        return "none"
    if args.silence_trim_engine != "auto":
        return args.silence_trim_engine
    if has_stream(input_path, "video") and not args.no_video_copy:
        return "concat"
    if args.cut_transition != "none" or args.video_cut_transition not in {"match", "none"}:
        return "concat"
    return "silenceremove"


def resolve_video_transition(args: argparse.Namespace) -> str:
    """Определя video transition режима, когато се реже видео."""

    if args.video_cut_transition == "match":
        return args.cut_transition
    return args.video_cut_transition


def clamp_fade_duration(duration: float, ranges: Sequence[TimeRange]) -> float:
    """Ограничава fade duration така, че да не е по-дълъг от кратък сегмент."""

    if duration <= 0 or not ranges:
        return 0.0
    shortest = min(item.duration for item in ranges)
    return max(0.0, min(duration, shortest / 3))


def format_seconds(value: float) -> str:
    """Форматира секунди за FFmpeg filters с millisecond точност."""

    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


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


def relative_band_levels(bands: dict[str, float], mean_volume_db: float | None) -> dict[str, float]:
    """Преобразува абсолютните band нива към относителни стойности спрямо общия mean volume."""
    if mean_volume_db is None:
        return {}
    return {name: value - mean_volume_db for name, value in bands.items()}


def classify_audio_content(analysis: AudioAnalysis, requested_type: str) -> tuple[str, float]:
    """Класифицира съдържанието като speech/music/other чрез консервативни heuristics."""
    if requested_type != "auto":
        return requested_type, 1.0

    rel = analysis.spectral_relative_db
    silence_ratio = analysis.silence_ratio or 0.0
    channels = analysis.technical.channels or 0

    speech_score = 0.10
    music_score = 0.10

    if 0.03 <= silence_ratio <= 0.45:
        speech_score += 0.25
    if silence_ratio < 0.12:
        music_score += 0.15
    if channels >= 2:
        music_score += 0.15
    if channels == 1:
        speech_score += 0.15

    if rel.get("presence", -99) > rel.get("air", -99) + 6:
        speech_score += 0.20
    if rel.get("low_mid", -99) > rel.get("sub", -99) + 4:
        speech_score += 0.10
    if rel.get("bass", -99) > -18 and rel.get("air", -99) > -30:
        music_score += 0.25
    if rel.get("sub", -99) > -20 and rel.get("air", -99) > -28:
        music_score += 0.10

    lra = analysis.loudness_range_lu
    if lra is not None:
        if 4 <= lra <= 18:
            speech_score += 0.10
        if 2 <= lra <= 14:
            music_score += 0.10

    if analysis.mean_volume_db is not None and analysis.mean_volume_db < -55:
        return "other", 0.45

    scores = {"speech": speech_score, "music": music_score}
    content_type, score = max(scores.items(), key=lambda item: item[1])
    confidence = min(0.95, max(0.35, score))
    if abs(speech_score - music_score) < 0.10 and confidence < 0.70:
        return "other", 0.45
    return content_type, confidence


def analyze_audio_file(input_path: Path, args: argparse.Namespace) -> AudioAnalysis:
    """Изпълнява пълен практически анализ за диагностика и препоръки."""
    technical = get_audio_technical_info(input_path)
    target_for_analysis = args.loudness_target
    if target_for_analysis is None:
        target_for_analysis = DEFAULT_LOUDNESS_TARGETS["speech"]

    print(f"Анализирам технически параметри, нива, loudness, тишина и честотен баланс: {input_path}")
    volume_stats = analyze_volume_stats(input_path, args.analysis_seconds)
    loudnorm_stats = analyze_loudnorm_stats(
        input_path,
        target_for_analysis,
        args.true_peak_target,
        args.lra_target,
        args.analysis_seconds,
    )
    silence_segments, silence_ratio = detect_silence_segments(
        input_path,
        technical.duration,
        args.analysis_seconds,
        args.silence_threshold,
        args.silence_duration,
    )
    spectral_bands = analyze_spectral_bands(input_path, args.analysis_seconds)
    spectral_relative = relative_band_levels(spectral_bands, volume_stats.get("mean_volume_db"))

    channel_peaks: list[float] = []
    if technical.channels and 1 < technical.channels <= 8:
        channel_peaks = analyze_channel_peaks(input_path, technical.channels)

    analysis = AudioAnalysis(
        input_file=str(input_path),
        technical=technical,
        max_peak_db=volume_stats.get("max_peak_db"),
        mean_volume_db=volume_stats.get("mean_volume_db"),
        integrated_lufs=loudnorm_stats.get("input_i"),
        true_peak_db=loudnorm_stats.get("input_tp"),
        loudness_range_lu=loudnorm_stats.get("input_lra"),
        loudness_threshold_lufs=loudnorm_stats.get("input_thresh"),
        silence_ratio=silence_ratio,
        silence_segments=len(silence_segments),
        channel_peaks_db=channel_peaks,
        spectral_bands_db=spectral_bands,
        spectral_relative_db=spectral_relative,
    )
    analysis.detected_content_type, analysis.content_confidence = classify_audio_content(analysis, args.content_type)

    if args.analysis_seconds > 0:
        analysis.notes.append(
            f"Част от анализа е ограничена до първите {args.analysis_seconds:g} секунди; "
            "за финално решение върху целия файл използвай --analysis-seconds 0."
        )
    if analysis.content_confidence < 0.65 and args.content_type == "auto":
        analysis.notes.append(
            "Автоматичното разпознаване е с ниска увереност; препоръките са предпазливи. "
            "За по-точен резултат задай --content-type speech, music или other."
        )
    return analysis


def has_channel_imbalance(analysis: AudioAnalysis, threshold: float) -> bool:
    """Проверява дали channel peak разликата предполага нужда от balance."""
    if len(analysis.channel_peaks_db) < 2:
        return False
    return max(analysis.channel_peaks_db) - min(analysis.channel_peaks_db) > threshold


def build_audio_recommendation(analysis: AudioAnalysis, args: argparse.Namespace) -> AudioRecommendation:
    """Изгражда човешки проверима и FFmpeg-приложима препоръка от анализа."""
    content_type = analysis.detected_content_type
    target_lufs = args.loudness_target
    if target_lufs is None:
        target_lufs = DEFAULT_LOUDNESS_TARGETS.get(content_type, DEFAULT_LOUDNESS_TARGETS["other"])

    recommendation = AudioRecommendation(
        content_type=content_type,
        confidence=analysis.content_confidence,
        target_lufs=target_lufs,
        target_true_peak_db=args.true_peak_target,
        target_lra=args.lra_target,
        normalization_mode=resolve_normalization_mode(args),
    )

    def add_preset(name: str, reason: str) -> None:
        if name not in recommendation.preset_names:
            recommendation.preset_names.append(name)
            recommendation.filters.extend(PRESETS[name])
        if reason not in recommendation.deficits:
            recommendation.deficits.append(reason)

    def add_filter(ffmpeg_filter: str, reason: str) -> None:
        if ffmpeg_filter not in recommendation.filters:
            recommendation.filters.append(ffmpeg_filter)
        if reason not in recommendation.deficits:
            recommendation.deficits.append(reason)

    rel = analysis.spectral_relative_db
    low_confidence = args.content_type == "auto" and analysis.content_confidence < 0.65

    if analysis.integrated_lufs is not None:
        if analysis.integrated_lufs < target_lufs - 3:
            recommendation.deficits.append(
                f"Ниско възприемано ниво: {analysis.integrated_lufs:.1f} LUFS при цел {target_lufs:.1f} LUFS."
            )
        elif analysis.integrated_lufs > target_lufs + 3:
            recommendation.deficits.append(
                f"Високо възприемано ниво: {analysis.integrated_lufs:.1f} LUFS при цел {target_lufs:.1f} LUFS."
            )

    peak = analysis.true_peak_db if analysis.true_peak_db is not None else analysis.max_peak_db
    if peak is not None and peak > args.true_peak_target + 1.0:
        recommendation.warnings.append(
            f"Peak/true peak е близо до цифровия максимум ({peak:.1f} dB); нормализацията трябва да остане последна."
        )

    if has_channel_imbalance(analysis, args.balance_threshold):
        difference = max(analysis.channel_peaks_db) - min(analysis.channel_peaks_db)
        recommendation.deficits.append(f"Канален imbalance около {difference:.1f} dB; препоръчва се channel balance.")

    if analysis.silence_ratio is not None and analysis.silence_ratio > 0.35:
        recommendation.warnings.append(
            f"Открита е много тишина ({analysis.silence_ratio * 100:.0f}% от анализа). "
            "Помисли за trim/split преди силна нормализация."
        )

    if not low_confidence:
        if content_type == "speech":
            if rel.get("sub", -99) > -18:
                add_filter("highpass=f=90", "Нискочестотен rumble под полезния говорен диапазон.")
            if rel.get("low_mid", -99) > -8:
                add_preset("de_mud", "Мътност в ниските среди около 200-500 Hz.")
            if rel.get("presence", -99) < -14:
                add_preset("presence_boost", "Недостатъчна разбираемост/presence за говор.")
            if rel.get("sibilance", -99) > -7:
                add_preset("sibilance_soften", "Вероятни сибиланти или острота във високите среди.")
            if not recommendation.filters:
                add_preset("speech_cleanup", "Базово почистване и яснота за говор.")
        elif content_type == "music":
            if rel.get("sub", -99) > -14:
                add_preset("bass_tighten", "Прекомерен sub/rumble или разхлабен нисък бас.")
            if rel.get("low_mid", -99) > -7:
                add_preset("de_mud", "Натрупване в ниските среди.")
            if rel.get("presence", -99) > -5:
                add_preset("harshness_reduce", "Вероятна острота в зоната 2.5-5 kHz.")
            if rel.get("air", -99) < -28:
                add_preset("air_boost", "Липса на въздух и най-високи честоти.")
            if not recommendation.filters:
                add_preset("soft_loudness_balance", "Лека тонална корекция за по-балансирано слушане.")
        else:
            if rel.get("sub", -99) > -16:
                add_preset("rumble_removal", "Нискочестотен rumble.")
            if rel.get("low_mid", -99) > -7:
                add_preset("boxiness_reduce", "Кутиест или стаен характер в ниските среди.")
    else:
        if rel.get("sub", -99) > -14:
            add_preset("rumble_removal", "Нискочестотен rumble при неясен тип съдържание.")
        recommendation.warnings.append("Ниска увереност в типа съдържание; избягват се агресивни EQ/denoise решения.")

    if not recommendation.filters:
        recommendation.deficits.append("Не са открити ясни тонални дефицити; препоръчва се само финална нормализация.")

    return recommendation


def print_analysis_report(analysis: AudioAnalysis) -> None:
    """Печата кратък, но изчерпателен отчет на български."""
    tech = analysis.technical
    print("\n=== Аудио анализ ===")
    print(f"Файл: {analysis.input_file}")
    print(f"Тип съдържание: {analysis.detected_content_type} (увереност {analysis.content_confidence:.2f})")
    print("Технически данни:")
    print(f"  продължителност: {tech.duration:.2f} s" if tech.duration else "  продължителност: неизвестна")
    print(f"  codec: {tech.codec or 'неизвестен'}")
    print(f"  sample rate: {tech.sample_rate or 'неизвестен'} Hz")
    print(f"  канали: {tech.channels or 'неизвестно'} ({tech.channel_layout or 'без layout'})")
    print(f"  bitrate: {tech.bit_rate or 'неизвестен'} bps")
    print("Нива:")
    print(format_optional_metric("  max sample peak", analysis.max_peak_db, "dBFS"))
    print(format_optional_metric("  mean volume", analysis.mean_volume_db, "dB"))
    print(format_optional_metric("  integrated loudness", analysis.integrated_lufs, "LUFS"))
    print(format_optional_metric("  true peak", analysis.true_peak_db, "dBTP"))
    print(format_optional_metric("  loudness range", analysis.loudness_range_lu, "LU"))
    if analysis.silence_ratio is not None:
        print(f"  тишина: {analysis.silence_segments} сегмента, приблизително {analysis.silence_ratio * 100:.1f}%")
    else:
        print(f"  тишина: {analysis.silence_segments} сегмента, дял неизвестен")
    if analysis.channel_peaks_db:
        print("Канали:")
        for index, peak in enumerate(analysis.channel_peaks_db, 1):
            print(f"  канал {index}: {peak:.2f} dBFS")
    if analysis.spectral_relative_db:
        print("Честотен баланс спрямо общото mean ниво:")
        for name, (_, _, description) in SPECTRAL_BANDS.items():
            if name in analysis.spectral_relative_db:
                print(f"  {name:10s} {analysis.spectral_relative_db[name]:+6.1f} dB  ({description})")
    for note in analysis.notes:
        print(f"Бележка: {note}")


def format_optional_metric(label: str, value: float | None, unit: str) -> str:
    """Форматира метрика с липсваща стойност без двусмислие."""
    if value is None:
        return f"{label}: неизвестно"
    return f"{label}: {value:.2f} {unit}"


def print_recommendation(recommendation: AudioRecommendation) -> None:
    """Печата препоръката в CLI-четим вид."""
    print("\n=== Препоръка ===")
    print(f"Тип: {recommendation.content_type} (увереност {recommendation.confidence:.2f})")
    print(
        "Финална нормализация: "
        f"{recommendation.normalization_mode}, I={recommendation.target_lufs:g} LUFS, "
        f"TP={recommendation.target_true_peak_db:g} dBTP, LRA={recommendation.target_lra:g} LU"
    )
    if recommendation.deficits:
        print("Установени дефицити:")
        for item in recommendation.deficits:
            print(f"  - {item}")
    if recommendation.preset_names:
        print("Препоръчани preset-и:")
        for name in recommendation.preset_names:
            print(f"  - {name}: {PRESET_DESCRIPTIONS.get(name, 'Няма описание.')}")
    if recommendation.filters:
        print("Препоръчана FFmpeg filter chain преди нормализация:")
        print(f"  {','.join(recommendation.filters)}")
    if recommendation.warnings:
        print("Предупреждения:")
        for item in recommendation.warnings:
            print(f"  - {item}")


def write_analysis_json(
    output_path: Path,
    analysis: AudioAnalysis,
    recommendation: AudioRecommendation | None,
) -> None:
    """Записва анализа и препоръката в JSON файл с UTF-8 текст."""
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis": asdict(analysis),
        "recommendation": asdict(recommendation) if recommendation else None,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Записан JSON отчет: {output_path}")


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
            "финалната нормализация остава задължителна последна стъпка."
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


def build_silence_trim_filter(args: argparse.Namespace) -> str:
    """Създава FFmpeg silenceremove filter за скъсяване на дълги паузи."""

    threshold = f"{args.silence_threshold:g}dB"
    duration = f"{args.silence_duration:g}"
    keep_start = resolve_keep_silence(args, "start")
    keep_middle = resolve_keep_silence(args, "middle")
    keep_end = resolve_keep_silence(args, "end")
    window = f"{args.silence_window:g}"
    scope = args.trim_silence_scope
    start_periods = 1 if scope in {"all", "edges", "start"} else 0
    if scope == "all":
        stop_periods = -1
        stop_keep = keep_middle
    elif scope == "middle":
        stop_periods = -1
        stop_keep = keep_middle
        print(
            "Предупреждение: --trim-silence-scope middle използва FFmpeg silenceremove с повторяем stop режим. "
            "Това е подходящо за вътрешни паузи, но може да засегне и крайна тишина."
        )
    elif scope in {"edges", "end"}:
        stop_periods = 1
        stop_keep = keep_end
    else:
        stop_periods = 0
        stop_keep = keep_middle

    parts = [f"silenceremove=start_periods={start_periods}"]
    if start_periods:
        parts.extend(
            [
                f"start_duration={duration}",
                f"start_threshold={threshold}",
                f"start_silence={keep_start:g}",
                f"start_mode={args.silence_channel_mode}",
            ]
        )

    parts.append(f"stop_periods={stop_periods}")
    if stop_periods:
        parts.extend(
            [
                f"stop_duration={duration}",
                f"stop_threshold={threshold}",
                f"stop_silence={stop_keep:g}",
                f"stop_mode={args.silence_channel_mode}",
            ]
        )

    parts.extend([f"detection={args.silence_detection}", f"window={window}"])
    return ":".join(parts)


def resolve_keep_silence(args: argparse.Namespace, position: str) -> float:
    """Връща keep-silence стойност за start/middle/end с fallback към --keep-silence."""

    attribute = {
        "start": "keep_start_silence",
        "middle": "keep_middle_silence",
        "end": "keep_end_silence",
    }[position]
    value = getattr(args, attribute, None)
    return args.keep_silence if value is None else value


def segment_audio_filter(
    index: int,
    time_range: TimeRange,
    audio_filters: Sequence[str],
    args: argparse.Namespace,
    fade_duration: float,
    transition: str,
    total_segments: int,
) -> str:
    """Създава filter_complex част за един audio segment."""

    filters = [
        f"[0:a:0]atrim=start={format_seconds(time_range.start)}:end={format_seconds(time_range.end)}",
        "asetpts=PTS-STARTPTS",
    ]
    filters.extend(audio_filters)
    if transition == "fade" and fade_duration > 0:
        if index > 0:
            filters.append(f"afade=t=in:st=0:d={format_seconds(fade_duration)}:curve={args.cut_fade_curve}")
        if index < total_segments - 1:
            start = max(0.0, time_range.duration - fade_duration)
            filters.append(
                f"afade=t=out:st={format_seconds(start)}:d={format_seconds(fade_duration)}:curve={args.cut_fade_curve}"
            )
    return ",".join(filters) + f"[a{index}]"


def segment_video_filter(
    index: int,
    time_range: TimeRange,
    args: argparse.Namespace,
    fade_duration: float,
    transition: str,
    total_segments: int,
) -> str:
    """Създава filter_complex част за един video segment."""

    filters = [
        f"[0:v:0]trim=start={format_seconds(time_range.start)}:end={format_seconds(time_range.end)}",
        "setpts=PTS-STARTPTS",
    ]
    if transition == "fade" and fade_duration > 0:
        if index > 0:
            filters.append(f"fade=t=in:st=0:d={format_seconds(fade_duration)}")
        if index < total_segments - 1:
            start = max(0.0, time_range.duration - fade_duration)
            filters.append(f"fade=t=out:st={format_seconds(start)}:d={format_seconds(fade_duration)}")
    return ",".join(filters) + f"[v{index}]"


def build_acrossfade_chain(segment_count: int, fade_duration: float, curve: str) -> tuple[list[str], str]:
    """Създава FFmpeg acrossfade chain за audio segments."""

    if segment_count == 1:
        return [], "[a0]"

    commands: list[str] = []
    previous = "[a0]"
    for index in range(1, segment_count):
        output = f"[ac{index}]"
        commands.append(
            f"{previous}[a{index}]"
            f"acrossfade=d={format_seconds(fade_duration)}:c1={curve}:c2={curve}"
            f"{output}"
        )
        previous = output
    return commands, previous


def build_xfade_chain(ranges: Sequence[TimeRange], fade_duration: float) -> tuple[list[str], str]:
    """Създава FFmpeg xfade chain за video segments."""

    if len(ranges) == 1:
        return [], "[v0]"

    commands: list[str] = []
    previous = "[v0]"
    accumulated_duration = ranges[0].duration
    for index in range(1, len(ranges)):
        output = f"[vx{index}]"
        offset = max(0.0, accumulated_duration - fade_duration)
        commands.append(
            f"{previous}[v{index}]"
            f"xfade=transition=fade:duration={format_seconds(fade_duration)}:offset={format_seconds(offset)}"
            f"{output}"
        )
        previous = output
        accumulated_duration = accumulated_duration + ranges[index].duration - fade_duration
    return commands, previous


def build_concat_filter_complex(
    ranges: Sequence[TimeRange],
    audio_filters: Sequence[str],
    args: argparse.Namespace,
    include_video: bool,
) -> tuple[str, str, str | None]:
    """Създава filter_complex за concat trim с optional audio/video transition-и."""

    fade_duration = clamp_fade_duration(args.cut_fade_duration, ranges)
    audio_transition = args.cut_transition if fade_duration > 0 else "none"
    video_transition = resolve_video_transition(args) if fade_duration > 0 else "none"
    commands: list[str] = []

    for index, time_range in enumerate(ranges):
        commands.append(segment_audio_filter(index, time_range, audio_filters, args, fade_duration, audio_transition, len(ranges)))
        if include_video:
            commands.append(segment_video_filter(index, time_range, args, fade_duration, video_transition, len(ranges)))

    if audio_transition == "crossfade" and len(ranges) > 1:
        audio_chain, audio_label = build_acrossfade_chain(len(ranges), fade_duration, args.cut_fade_curve)
        commands.extend(audio_chain)
    else:
        audio_inputs = "".join(f"[a{index}]" for index in range(len(ranges)))
        audio_label = "[aout]"
        commands.append(f"{audio_inputs}concat=n={len(ranges)}:v=0:a=1{audio_label}")

    video_label: str | None = None
    if include_video:
        if video_transition == "crossfade" and len(ranges) > 1:
            video_chain, video_label = build_xfade_chain(ranges, fade_duration)
            commands.extend(video_chain)
        else:
            video_inputs = "".join(f"[v{index}]" for index in range(len(ranges)))
            video_label = "[vout]"
            commands.append(f"{video_inputs}concat=n={len(ranges)}:v=1:a=0{video_label}")

    return ";".join(commands), audio_label, video_label


def build_concat_trim_command(
    input_path: Path,
    output_path: Path,
    ranges: Sequence[TimeRange],
    audio_filters: Sequence[str],
    args: argparse.Namespace,
) -> list[str]:
    """Създава FFmpeg команда за concat-based silence trim със синхронно audio/video рязане."""

    include_video = has_stream(input_path, "video") and not args.no_video_copy
    filter_complex, audio_label, video_label = build_concat_filter_complex(ranges, audio_filters, args, include_video)
    codec = choose_audio_codec(output_path, args.audio_codec, include_video)
    command = ["ffmpeg", "-hide_banner", "-y" if args.overwrite else "-n", "-i", str(input_path), "-filter_complex", filter_complex]

    if include_video and video_label:
        command += ["-map", video_label, "-map", audio_label, "-c:v", "libx264", "-c:a", codec]
    else:
        command += ["-map", audio_label, "-vn", "-c:a", codec]

    if args.sample_rate:
        command += ["-ar", str(args.sample_rate)]
    if args.bitrate:
        command += ["-b:a", args.bitrate]

    command.append(str(output_path))
    return command


def apply_concat_silence_trim(
    input_path: Path,
    output_path: Path,
    audio_filters: Sequence[str],
    args: argparse.Namespace,
) -> None:
    """Прилага concat-based silence trim, нужен за fade/crossfade и video sync."""

    technical = get_audio_technical_info(input_path)
    if not technical.duration:
        raise SystemExit("Concat silence trim изисква известна продължителност на входния файл.")

    silence_segments, silence_ratio = detect_silence_segments(
        input_path,
        technical.duration,
        args.analysis_seconds,
        args.silence_threshold,
        args.silence_duration,
    )
    print_silence_report(input_path, silence_segments, silence_ratio, args)
    removed_ranges = build_removed_silence_ranges(silence_segments, args)
    kept_ranges = build_kept_time_ranges(technical.duration, removed_ranges)
    if not removed_ranges or len(kept_ranges) == 1:
        print("Concat silence trim: няма паузи за изрязване; прилага се само pre-normalization filter stage.")
        apply_eq_filters(input_path, output_path, audio_filters, args)
        return

    print("Concat silence trim: запазени сегменти:")
    for index, time_range in enumerate(kept_ranges, start=1):
        print(f"  {index:02d}. {time_range.start:.3f}s -> {time_range.end:.3f}s ({time_range.duration:.3f}s)")

    command = build_concat_trim_command(input_path, output_path, kept_ranges, audio_filters, args)
    run_command(command, dry_run=args.dry_run)


def collect_pre_normalization_filters(
    input_path: Path,
    args: argparse.Namespace,
    eq_filters: Sequence[str],
    *,
    include_silenceremove: bool = True,
) -> list[str]:
    """Създава filter chain преди нормализация: balance -> EQ/филтри -> silence trim."""
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
    if args.trim_silence and include_silenceremove:
        filters.append(build_silence_trim_filter(args))
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


def build_measured_loudnorm_filter(
    measured: dict[str, float | None],
    target_lufs: float,
    true_peak_target: float,
    lra_target: float,
) -> str:
    """Създава loudnorm filter, предпочитайки двупасови measured параметри, когато са налични."""
    base = f"loudnorm=I={target_lufs:g}:TP={true_peak_target:g}:LRA={lra_target:g}"
    required = ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]
    if not all(measured.get(key) is not None for key in required):
        return f"{base}:print_format=summary"

    return (
        f"{base}:"
        f"measured_I={measured['input_i']:.6g}:"
        f"measured_TP={measured['input_tp']:.6g}:"
        f"measured_LRA={measured['input_lra']:.6g}:"
        f"measured_thresh={measured['input_thresh']:.6g}:"
        f"offset={measured['target_offset']:.6g}:"
        "linear=true:print_format=summary"
    )


def resolve_loudness_target(content_type: str, args: argparse.Namespace) -> float:
    """Избира LUFS target от CLI или от типа съдържание."""
    if args.loudness_target is not None:
        return args.loudness_target
    return DEFAULT_LOUDNESS_TARGETS.get(content_type, DEFAULT_LOUDNESS_TARGETS["other"])


def resolve_normalization_mode(args: argparse.Namespace) -> str:
    """Определя финалната нормализация според режима на работа."""
    if args.normalization_mode:
        return args.normalization_mode
    if args.apply_recommendation:
        return "loudness"
    return "peak"


def apply_loudness_normalization(
    input_path: Path,
    output_path: Path,
    content_type: str,
    args: argparse.Namespace,
) -> None:
    """Прилага EBU R128 loudnorm като финален етап."""
    target_lufs = resolve_loudness_target(content_type, args)
    render_args = argparse.Namespace(**vars(args))
    if not render_args.sample_rate:
        render_args.sample_rate = get_audio_technical_info(input_path).sample_rate

    if args.dry_run:
        loudnorm_filter = (
            f"loudnorm=I={target_lufs:g}:TP={args.true_peak_target:g}:"
            f"LRA={args.lra_target:g}:print_format=summary"
        )
        print("Dry run: loudnorm measured pass се пропуска; показва се еднопасовата команда.")
        command = build_ffmpeg_command(input_path, output_path, [loudnorm_filter], render_args)
        run_command(command, dry_run=True)
        return

    print(
        "Анализирам loudness за финална нормализация: "
        f"I={target_lufs:g} LUFS, TP={args.true_peak_target:g} dBTP, LRA={args.lra_target:g} LU"
    )
    measured = analyze_loudnorm_stats(input_path, target_lufs, args.true_peak_target, args.lra_target, 0)
    loudnorm_filter = build_measured_loudnorm_filter(measured, target_lufs, args.true_peak_target, args.lra_target)
    command = build_ffmpeg_command(input_path, output_path, [loudnorm_filter], render_args)
    run_command(command, dry_run=False)


def apply_final_normalization(
    input_path: Path,
    output_path: Path,
    content_type: str,
    args: argparse.Namespace,
) -> None:
    """Прилага избрания финален normalization режим."""
    mode = resolve_normalization_mode(args)
    if mode == "loudness":
        apply_loudness_normalization(input_path, output_path, content_type, args)
    else:
        apply_peak_normalization(input_path, output_path, args.target_level, args)


def validate_paths(args: argparse.Namespace) -> tuple[Path, Path | None]:
    """Проверява входния и изходния път преди началото на обработката."""
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else None

    if not input_path.is_file():
        raise SystemExit(f"Входният файл не съществува: {input_path}")
    if input_path.suffix.lower() not in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS:
        print(f"Предупреждение: непознато разширение '{input_path.suffix}'; опитвам FFmpeg обработка въпреки това.")
    if output_path is None:
        return input_path, None
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"Изходният файл съществува: {output_path}. Използвай --overwrite за презапис.")
    if input_path == output_path:
        raise SystemExit("Входният и изходният път трябва да са различни.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return input_path, output_path


def main() -> int:
    """Координира parser-а, анализа, препоръките, filter етапа и финалното рендериране."""
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
    silence_trim_engine = resolve_silence_trim_engine(args, input_path)
    if args.trim_silence and silence_trim_engine == "silenceremove":
        if has_stream(input_path, "video") and not args.no_video_copy:
            raise SystemExit(
                "silenceremove trim при видео вход би разсинхронизирал аудио и видео. "
                "Използвай --silence-trim-engine concat или --no-video-copy."
            )
        if args.cut_transition != "none" or resolve_video_transition(args) != "none":
            raise SystemExit("Fade/crossfade transition-и изискват --silence-trim-engine concat.")

    if args.analyze_silence:
        technical = get_audio_technical_info(input_path)
        silence_segments, silence_ratio = detect_silence_segments(
            input_path,
            technical.duration,
            args.analysis_seconds,
            args.silence_threshold,
            args.silence_duration,
        )
        print_silence_report(input_path, silence_segments, silence_ratio, args)
        if not (args.analyze_audio or args.recommend_processing or args.apply_recommendation):
            print("Готово: анализът на тишина приключи без обработка на файл.")
            return 0

    analysis: AudioAnalysis | None = None
    recommendation: AudioRecommendation | None = None
    if args.analyze_audio or args.recommend_processing or args.apply_recommendation:
        analysis = analyze_audio_file(input_path, args)
        print_analysis_report(analysis)

    if analysis and (args.recommend_processing or args.apply_recommendation):
        recommendation = build_audio_recommendation(analysis, args)
        print_recommendation(recommendation)

    if args.analysis_json:
        if analysis is None:
            analysis = analyze_audio_file(input_path, args)
            print_analysis_report(analysis)
        if recommendation is None and (args.recommend_processing or args.apply_recommendation):
            recommendation = build_audio_recommendation(analysis, args)
        write_analysis_json(Path(args.analysis_json), analysis, recommendation)

    if args.analyze_audio and not args.recommend_processing and not args.apply_recommendation:
        print("Готово: анализът приключи без обработка на файл.")
        return 0

    if args.recommend_processing and not args.apply_recommendation:
        print("Готово: препоръката е изведена без обработка на файл.")
        return 0

    if output_path is None:
        raise SystemExit("-o/--output е задължителен при обработка.")

    recommended_filters: list[str] = []
    content_type_for_normalization = args.content_type if args.content_type != "auto" else "other"
    if recommendation:
        recommended_filters = recommendation.filters
        content_type_for_normalization = recommendation.content_type
        if analysis and has_channel_imbalance(analysis, args.balance_threshold):
            print("Автоматичната препоръка включва channel balance заради измерена канална разлика.")
            args.balance_channels = True

    if not recommendation and analysis:
        content_type_for_normalization = analysis.detected_content_type

    eq_filters = recommended_filters + eq_filters
    pre_filters = collect_pre_normalization_filters(
        input_path,
        args,
        eq_filters,
        include_silenceremove=silence_trim_engine == "silenceremove",
    )

    has_concat_trim = args.trim_silence and silence_trim_engine == "concat"
    if not pre_filters and not has_concat_trim:
        if args.balance_channels:
            print("Не е приложен channel balance и не е избран EQ; прилагам само финална нормализация.")
        else:
            print("Не е избран EQ/channel balance/silence trim; прилагам само финална нормализация.")
        apply_final_normalization(input_path, output_path, content_type_for_normalization, args)
        print("Готово.")
        return 0

    print("Ред на обработка: channel balance -> филтри/EQ -> silence trim -> финална нормализация.")
    with tempfile.TemporaryDirectory(prefix="audio_peak_eq_") as temp_dir:
        temp_suffix = output_path.suffix if has_stream(input_path, "video") else ".wav"
        temp_path = Path(temp_dir) / f"pre_normalize_stage{temp_suffix}"
        stage_args = argparse.Namespace(**vars(args))
        stage_args.overwrite = True

        print(f"Временен pre-normalization файл: {temp_path}")
        if has_concat_trim:
            apply_concat_silence_trim(input_path, temp_path, pre_filters, stage_args)
        else:
            apply_eq_filters(input_path, temp_path, pre_filters, stage_args)
        apply_final_normalization(temp_path, output_path, content_type_for_normalization, args)

        if args.keep_temp and not args.dry_run:
            kept_path = output_path.with_name(f"{output_path.stem}.pre_normalize_stage{output_path.suffix}")
            shutil.copy2(temp_path, kept_path)
            print(f"Запазен pre-normalization stage файл: {kept_path}")

    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
