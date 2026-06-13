from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from tests.helpers.importing import import_module_from_path
from tests.helpers.media_factory import make_imbalanced_stereo_wav, make_sine_wav, make_test_mp4

pytestmark = [pytest.mark.unit, pytest.mark.media]


@pytest.fixture(scope="module")
def audio_peak_eq(repo_root: Path):
    return import_module_from_path(
        repo_root / "tools" / "media" / "audio" / "python" / "audio_peak_eq.py",
        "audio_peak_eq_tool",
    )


def _args(**overrides):
    values = {
        "audio_codec": "auto",
        "overwrite": True,
        "no_video_copy": False,
        "sample_rate": None,
        "bitrate": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_parse_ffmpeg_max_volume(audio_peak_eq) -> None:
    output = "[Parsed_volumedetect_0] max_volume: -3.4 dB\n"
    assert audio_peak_eq.parse_ffmpeg_max_volume(output) == -3.4


def test_parse_ffmpeg_max_volume_rejects_silence(audio_peak_eq) -> None:
    with pytest.raises(SystemExit):
        audio_peak_eq.parse_ffmpeg_max_volume("max_volume: -inf dB")


def test_collect_eq_filters_uses_preset_then_custom(audio_peak_eq) -> None:
    args = argparse.Namespace(preset="bass_boost", eq_filter=["highpass=f=40"])
    filters = audio_peak_eq.collect_eq_filters(args)
    assert filters[:2] == audio_peak_eq.PRESETS["bass_boost"]
    assert filters[-1] == "highpass=f=40"


def test_choose_audio_codec(audio_peak_eq) -> None:
    assert audio_peak_eq.choose_audio_codec(Path("out.wav"), "auto", False) == "pcm_s16le"
    assert audio_peak_eq.choose_audio_codec(Path("out.mp3"), "auto", False) == "libmp3lame"
    assert audio_peak_eq.choose_audio_codec(Path("out.bin"), "copy", False) == "copy"


def test_build_ffmpeg_command_for_audio(audio_peak_eq, tmp_path: Path) -> None:
    input_wav = make_sine_wav(tmp_path / "in.wav")
    output_wav = tmp_path / "out.wav"

    command = audio_peak_eq.build_ffmpeg_command(
        input_wav,
        output_wav,
        ["volume=-1dB"],
        _args(),
    )

    assert "-af" in command
    assert "volume=-1dB" in command
    assert "-vn" in command
    assert "-c:a" in command
    assert str(output_wav) == command[-1]


def test_build_ffmpeg_command_for_video_copies_video(audio_peak_eq, tmp_path: Path) -> None:
    input_mp4 = make_test_mp4(tmp_path / "in.mp4")
    output_mp4 = tmp_path / "out.mp4"

    command = audio_peak_eq.build_ffmpeg_command(
        input_mp4,
        output_mp4,
        ["volume=-1dB"],
        _args(),
    )

    assert "-map" in command
    assert "-c:v" in command
    assert "copy" in command
    assert "-c:s" in command


def test_build_channel_balance_filter_for_stereo(audio_peak_eq) -> None:
    balance_filter = audio_peak_eq.build_channel_balance_filter(
        [-3.0, -9.0],
        threshold=0.25,
        mode="stereo",
    )

    assert balance_filter is not None
    assert balance_filter.startswith("pan=stereo|")
    assert "c0=1*c0" in balance_filter
    assert "c1=1.99526231*c1" in balance_filter


def test_build_channel_balance_filter_for_multichannel_all(audio_peak_eq) -> None:
    balance_filter = audio_peak_eq.build_channel_balance_filter(
        [-3.0, -6.0, -9.0],
        threshold=0.25,
        mode="all",
    )

    assert balance_filter is not None
    assert balance_filter.startswith("pan=3c|")
    assert "c0=1*c0" in balance_filter
    assert "c1=1.41253754*c1" in balance_filter
    assert "c2=1.99526231*c2" in balance_filter


def test_build_channel_balance_filter_skips_below_threshold(audio_peak_eq) -> None:
    assert audio_peak_eq.build_channel_balance_filter([-3.0, -3.1], threshold=0.25, mode="stereo") is None


def test_build_channel_balance_filter_skips_non_stereo_in_stereo_mode(audio_peak_eq) -> None:
    assert audio_peak_eq.build_channel_balance_filter([-3.0, -6.0, -9.0], threshold=0.25, mode="stereo") is None


def test_channel_count_and_peak_analysis_for_stereo_fixture(audio_peak_eq, tmp_path: Path) -> None:
    input_wav = make_imbalanced_stereo_wav(tmp_path / "imbalanced.wav")

    channel_count = audio_peak_eq.get_audio_channel_count(input_wav)
    peaks = audio_peak_eq.analyze_channel_peaks(input_wav, channel_count)

    assert channel_count == 2
    assert len(peaks) == 2
    assert peaks[0] > peaks[1]
    assert 4.0 <= peaks[0] - peaks[1] <= 8.0
