from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest

from audio_metadata_normalizer.utils import (
    album,
    chapters,
    chapter_workflow,
    files,
    local_metadata,
    provider_workflow,
    rename,
    sfa_split,
)
from audio_metadata_normalizer.utils import dir_rename

pytestmark = pytest.mark.unit


class FakeProvider:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self.results = results or []

    def search(self, artist: str, album: str) -> list[dict[str, Any]]:
        assert artist == "Artist"
        assert album == "Album"
        return self.results

    def pick_best(self, results: list[dict[str, Any]], artist: str, album: str) -> dict[str, Any] | None:
        return results[0] if results else None

    def extract_metadata(self, release: dict[str, Any]) -> dict[str, Any]:
        return {"title": release["title"], "year": "2024"}

    def build_trackmap(self, release: dict[str, Any]) -> list[dict[str, str]]:
        return release["tracks"]


class FailingProvider(FakeProvider):
    def search(self, artist: str, album: str) -> list[dict[str, Any]]:
        raise URLError("Temporary failure in name resolution")


def test_chapter_parse_generate_roundtrip(tmp_path: Path) -> None:
    chapter_file = tmp_path / "chapters.txt"
    expected = [
        {"start": "00:00:00.000", "title": "Intro"},
        {"start": "00:03:10.000", "title": "Song"},
    ]

    chapters.generate_chapter_file(expected, str(chapter_file))

    assert chapter_file.read_text(encoding="utf-8").splitlines()[:5] == [
        "# albumtool chapters format: human-v1",
        "# Редактирай заглавието и началния момент под него във формат HH:MM:SS.mmm.",
        "",
        "Intro",
        "00:00:00.000",
    ]
    assert chapters.parse_chapter_file(str(chapter_file)) == expected


def test_chapter_parser_accepts_colon_before_milliseconds(tmp_path: Path) -> None:
    chapter_file = tmp_path / "chapters.txt"
    chapter_file.write_text(
        "Intro\n"
        "00:00:00.000\n\n"
        "Song\n"
        "00:21:18:030\n",
        encoding="utf-8",
    )

    assert chapters.parse_chapter_file(str(chapter_file)) == [
        {"title": "Intro", "start": "00:00:00.000"},
        {"title": "Song", "start": "00:21:18.030"},
    ]


def test_ogm_chapter_parse_generate_roundtrip(tmp_path: Path) -> None:
    chapter_file = tmp_path / "chapters.txt"
    expected = [
        {"start": "00:00:00.000", "title": "Intro"},
        {"start": "00:03:10.000", "title": "Song"},
    ]

    chapters.generate_ogm_chapter_file(expected, str(chapter_file))

    assert chapters.parse_ogm_chapter_file(str(chapter_file)) == expected
    assert chapters.parse_chapter_file(str(chapter_file)) == expected


def test_chapter_parser_ignores_malformed_and_incomplete_entries(tmp_path: Path) -> None:
    chapter_file = tmp_path / "bad_chapters.txt"
    chapter_file.write_text(
        "CHAPTER01=00:00:00.000\n"
        "CHAPTER01NAME=Intro\n"
        "CHAPTERXX=not-a-time\n"
        "CHAPTER02=00:02:00.000\n"
        "NO_EQUALS\n",
        encoding="utf-8",
    )

    assert chapters.parse_ogm_chapter_file(str(chapter_file)) == [
        {"start": "00:00:00.000", "title": "Intro"}
    ]


def test_chapter_workflow_paths_and_validation(tmp_path: Path) -> None:
    audio_file = tmp_path / "album.m4a"
    audio_file.write_bytes(b"fake")

    assert chapter_workflow.resolve_chapter_output_path(str(tmp_path), None) == str(tmp_path / "chapters.txt")
    assert chapter_workflow.resolve_chapter_input_path(str(tmp_path), "custom.txt") == str(tmp_path / "custom.txt")

    plan = chapter_workflow.build_embed_chapters_plan(str(tmp_path), str(audio_file), None)
    assert plan["in_place"] is True
    assert plan["final_path"] == str(audio_file)
    assert os.path.basename(plan["tmp_out"]).startswith(".tmp_chapters_")

    assert chapter_workflow.validate_chapters([{"start": "00:00:00.000", "title": "Intro"}]) is True
    assert chapter_workflow.validate_chapters([{"start": "00:00:01.000", "title": "Late"}]) is False


def test_chapter_workflow_reports_invalid_timestamp(tmp_path: Path, capsys) -> None:
    chapter_file = tmp_path / "chapters.txt"
    chapter_file.write_text("Intro\nnot-a-time\n", encoding="utf-8")

    assert chapter_workflow.load_chapters_for_embedding(str(chapter_file)) is None
    assert "Грешка в chapter файла" in capsys.readouterr().out


def test_sfa_chapter_paths_use_audio_stem_by_default(tmp_path: Path) -> None:
    audio_file = tmp_path / "Artist - 2024 - Live Album.m4a"
    audio_file.write_bytes(b"fake")

    assert chapter_workflow.resolve_sfa_chapter_output_path(str(audio_file), None) == str(
        tmp_path / "Artist - 2024 - Live Album.chapters.txt"
    )
    assert chapter_workflow.resolve_sfa_chapter_input_path(str(audio_file), None) == str(
        tmp_path / "Artist - 2024 - Live Album.chapters.txt"
    )
    assert chapter_workflow.resolve_sfa_audio_output_path(str(audio_file), "{stem}.tagged.m4a") == str(
        tmp_path / "Artist - 2024 - Live Album.tagged.m4a"
    )


def test_sfa_file_discovery_and_album_guessing(tmp_path: Path) -> None:
    first = tmp_path / "Artist - 2024 - Live Album.m4a"
    second = tmp_path / "Artist - 2025 - Other Album.mp3"
    ignored = tmp_path / "notes.txt"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    ignored.write_text("no audio", encoding="utf-8")

    assert files.resolve_sfa_audio_files([str(first)], [str(tmp_path / "*.mp3")]) == [
        str(first),
        str(second),
    ]
    assert album.guess_artist_album_from_audio_file(str(first)) == ("Artist", "Live Album")


def test_local_metadata_builds_trackmap_from_file_names(tmp_path: Path) -> None:
    first = tmp_path / "01 - Opening Chapter.mp3"
    second = tmp_path / "02_Second Chapter.flac"
    first.write_bytes(b"1")
    second.write_bytes(b"2")

    assert local_metadata.build_local_album_metadata("Book") == {
        "title": "Book",
        "year": None,
        "genres": [],
        "label": None,
        "catno": None,
    }
    assert local_metadata.build_local_trackmap(str(tmp_path)) == [
        {"title": "Opening Chapter", "source_track_number": 1},
        {"title": "Second Chapter", "source_track_number": 2},
    ]
    assert local_metadata.build_local_matched_tracks(str(tmp_path)) == [
        (str(first), {"title": "Opening Chapter", "source_track_number": 1}, 1.0),
        (str(second), {"title": "Second Chapter", "source_track_number": 2}, 1.0),
    ]


def test_sfa_split_bitrate_uses_next_standard_value() -> None:
    assert sfa_split.choose_standard_bitrate_kbps(128_000, "mp3")[0] == 128
    assert sfa_split.choose_standard_bitrate_kbps(129_000, "mp3")[0] == 144
    assert sfa_split.choose_standard_bitrate_kbps(150_000, "aac")[0] == 160


def test_sfa_split_timestamp_accepts_colon_milliseconds() -> None:
    assert sfa_split.timestamp_to_seconds("00:21:18:030") == 1278.03


def test_sfa_split_segments_use_next_chapter_as_end(tmp_path: Path) -> None:
    chapters_list = [
        {"title": "Intro", "start": "00:00:00.000"},
        {"title": "Song", "start": "00:01:30.000"},
    ]

    segments = sfa_split.build_split_segments(
        chapters_list,
        str(tmp_path),
        ".mp3",
        duration_seconds=180.0,
    )

    assert segments[0].start == "00:00:00.000"
    assert segments[0].end == "00:01:30.000"
    assert segments[1].end == "00:03:00.000"
    assert Path(segments[0].output_path).name == "1-Intro.mp3"
    assert Path(segments[1].output_path).name == "2-Song.mp3"


def test_sfa_split_command_builds_safe_mp3_encoding(tmp_path: Path) -> None:
    segment = sfa_split.SplitSegment(
        index=1,
        title="Intro",
        start="00:00:00.000",
        end="00:01:00.000",
        output_path=str(tmp_path / "1-Intro.mp3"),
    )

    command = sfa_split.build_split_command(
        "album.mp3",
        segment,
        sfa_split.SPLIT_PROFILES["lexus-mp3"],
        144,
        48000,
        {"title": "Intro", "artist": "Artist", "album": "Album", "track": "1/2"},
        "cover.jpg",
    )

    assert "-ss" not in command
    assert "-to" not in command
    assert command[command.index("-af") + 1] == "atrim=start=0.000:end=60.000,asetpts=PTS-STARTPTS"
    assert ["-c:a", "libmp3lame"] == command[command.index("-c:a"): command.index("-c:a") + 2]
    assert ["-b:a", "144k"] == command[command.index("-b:a"): command.index("-b:a") + 2]
    assert ["-c:v", "copy"] == command[command.index("-c:v"): command.index("-c:v") + 2]
    assert ["-ar", "48000"] == command[command.index("-ar"): command.index("-ar") + 2]
    assert "-id3v2_version" in command
    assert "-vn" not in command


def test_provider_workflow_with_fake_provider() -> None:
    release = {"title": "Album", "tracks": [{"title": "One"}]}
    provider = FakeProvider([release])

    best = provider_workflow.find_best_release(provider, "Artist", "Album")
    assert best == release
    assert provider_workflow.build_release_data(provider, best) == (
        {"title": "Album", "year": "2024"},
        [{"title": "One"}],
    )


def test_provider_workflow_handles_network_errors(capsys) -> None:
    best = provider_workflow.find_best_release(FailingProvider(), "Artist", "Album")

    assert best is None
    output = capsys.readouterr().out
    assert "Грешка при търсене на metadata" in output
    assert "Провери интернет връзката" in output


def test_rename_plan_conflict_detection(tmp_path: Path) -> None:
    first = tmp_path / "one.mp3"
    second = tmp_path / "two.mp3"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    target = tmp_path / "target.mp3"

    plan = [
        (str(first), str(target), {"title": "One"}, 1.0),
        (str(second), str(target), {"title": "Two"}, 1.0),
    ]

    assert rename.rename_plan_has_conflicts(plan) is True


def test_apply_rename_plan_rolls_back_when_temp_exists(tmp_path: Path) -> None:
    source = tmp_path / "one.mp3"
    source.write_bytes(b"1")
    target = tmp_path / "renamed.mp3"
    temp_collision = tmp_path / ".tmp_rename_1_one.mp3"
    temp_collision.write_bytes(b"collision")

    result = rename.apply_rename_plan(
        [(str(source), str(target), {"title": "One"}, 1.0)],
        dry_run=False,
    )

    assert result == []
    assert source.exists()
    assert not target.exists()


def test_dir_rename_plan_and_conflict_detection(tmp_path: Path) -> None:
    album_dir = tmp_path / "Old"
    album_dir.mkdir()
    existing = tmp_path / "2024-Album"
    existing.mkdir()

    plan = dir_rename.build_album_dir_rename_plan(
        str(album_dir),
        {"title": "Album", "year": "2024-01-01"},
        "Artist",
        "year-title",
    )

    assert plan == (str(album_dir), str(existing))
    assert dir_rename.dir_rename_plan_has_conflicts([plan]) is True


def test_album_dir_release_safe_match_checks_year(tmp_path: Path) -> None:
    album_dir = tmp_path / "2020-Album"
    album_dir.mkdir()

    assert dir_rename.album_dir_release_is_safe_match(
        str(album_dir),
        "Album",
        {"title": "Album", "year": "2024"},
        0.5,
    ) is False
