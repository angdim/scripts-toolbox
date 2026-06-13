from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.importing import import_module_from_path

pytestmark = pytest.mark.unit


def test_m4a2mp3_builds_expected_filter_chain(repo_root: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "audio" / "python" / "m4a2mp3_converter.py",
        "m4a2mp3_converter_tool",
    )
    settings = {
        "bitrate": "160k",
        "highpass": 80,
        "lowpass": 12000,
        "equalizer": ["1000:3:200"],
        "compressor": {
            "enabled": True,
            "threshold": -20,
            "ratio": 3,
            "attack": 5,
            "release": 50,
            "gain": 4,
        },
        "normalize": True,
    }

    filters = module.build_ffmpeg_filters(settings)

    assert filters is not None
    assert "highpass=f=80" in filters
    assert "lowpass=f=12000" in filters
    assert "equalizer=f=1000:g=3:width=200:width_type=h" in filters
    assert "acompressor=threshold=-20dB" in filters
    assert filters.endswith("loudnorm")


def test_m4a2mp3_dry_run_does_not_create_output(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "audio" / "python" / "m4a2mp3_converter.py",
        "m4a2mp3_converter_dry_run",
    )
    input_file = tmp_path / "demo.m4a"
    input_file.write_text("not real media", encoding="utf-8")

    ok = module.convert_file(input_file, {"bitrate": "128k"}, dry_run=True)

    assert ok is True
    assert not input_file.with_suffix(".mp3").exists()


def test_split_by_silence_segment_calculation(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "audio" / "python" / "split_by_silence.py",
        "split_by_silence_tool",
    )
    splitter = module.SilenceSplitter(tmp_path / "input.wav")
    splitter.get_duration = lambda: 20.0

    segments = splitter.calculate_segments([(4.0, 6.0), (10.0, 12.0)])

    assert segments == [(0, 4.0), (6.0, 10.0), (12.0, 20.0)]


def test_split_by_silence_filename_and_time_format(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "audio" / "python" / "split_by_silence.py",
        "split_by_silence_naming",
    )
    splitter = module.SilenceSplitter(
        tmp_path / "album.wav",
        output_format="flac",
        name_pattern="{name}_{num}_of_{total}",
    )

    assert splitter.generate_filename(3, 12) == "album_03_of_12.flac"
    assert splitter.format_time(65) == "01:05"
    assert splitter.format_time(3661) == "01:01:01"


def test_song_recognize_filename_helpers(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "speech" / "python" / "song_recognize.py",
        "song_recognize_tool",
    )
    recognizer = module.MusicRecognizer(tmp_path, output_dir=tmp_path / "out")

    assert recognizer.sanitize_filename(' Artist: / Song?  ') == "Artist Song"
    assert recognizer.extract_track_number("03 - demo") == "03"
    assert recognizer.extract_track_number("track_07_demo") == "07"
    assert recognizer.generate_new_filename(Path("03 - old.mp3"), "Title", "Artist") == "03 - Artist - Title.mp3"


def test_song_recognize_process_file_with_mocked_recognition(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "speech" / "python" / "song_recognize.py",
        "song_recognize_process",
    )
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "01 old.mp3"
    source.write_bytes(b"fake audio")
    output_dir = tmp_path / "out"
    recognizer = module.MusicRecognizer(input_dir, output_dir=output_dir, delay=0)

    async def fake_recognize(_: Path) -> tuple[str, str, str]:
        return "Song/Title?", "Artist:Name", "Album"

    recognizer.recognize_file = fake_recognize

    result = asyncio.run(recognizer.process_file(source))

    assert result is True
    assert (output_dir / "01 - ArtistName - SongTitle.mp3").exists()
    assert recognizer.recognized == 1


def test_split_recognize_filename_helpers(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "speech" / "python" / "split_recognize.py",
        "split_recognize_tool",
    )
    splitter = module.SilenceSplitter(tmp_path / "mix.wav", output_format="mp3", name_pattern="part_{num}")

    assert splitter.generate_filename(2, 12) == "02 - part_02.mp3"
    assert splitter.generate_recognized_filename(2, 12, "Song?", "Artist/Name") == "02 - ArtistName - Song.mp3"
    assert splitter.sanitize_filename(" bad:/name? ") == "badname"


def test_split_recognize_process_and_recognize_fallback(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "speech" / "python" / "split_recognize.py",
        "split_recognize_process",
    )
    splitter = module.SilenceSplitter(tmp_path / "mix.wav", output_format="mp3")
    splitter.output_dir = tmp_path / "out"
    splitter.output_dir.mkdir(exist_ok=True)
    temp_file = tmp_path / "temp.mp3"
    temp_file.write_bytes(b"fake")
    fallback = splitter.output_dir / "01 - fallback.mp3"

    async def fake_recognize(_: Path) -> tuple[Any, Any]:
        return None, None

    splitter.recognize_track = fake_recognize

    result = asyncio.run(splitter.process_and_recognize(temp_file, fallback, 1, 1))

    assert result is False
    assert fallback.exists()
    assert not temp_file.exists()
    assert splitter.recognition_failed == 1
