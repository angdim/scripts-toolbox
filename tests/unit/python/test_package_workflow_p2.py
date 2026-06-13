from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from audio_metadata_normalizer.utils import chapters, chapter_workflow, provider_workflow, rename
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


def test_chapter_parse_generate_roundtrip(tmp_path: Path) -> None:
    chapter_file = tmp_path / "chapters.txt"
    expected = [
        {"start": "00:00:00.000", "title": "Intro"},
        {"start": "00:03:10.000", "title": "Song"},
    ]

    chapters.generate_ogm_chapter_file(expected, str(chapter_file))

    assert chapters.parse_ogm_chapter_file(str(chapter_file)) == expected


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


def test_provider_workflow_with_fake_provider() -> None:
    release = {"title": "Album", "tracks": [{"title": "One"}]}
    provider = FakeProvider([release])

    best = provider_workflow.find_best_release(provider, "Artist", "Album")
    assert best == release
    assert provider_workflow.build_release_data(provider, best) == (
        {"title": "Album", "year": "2024"},
        [{"title": "One"}],
    )


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
