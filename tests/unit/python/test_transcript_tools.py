from __future__ import annotations

from pathlib import Path

from tests.helpers.importing import import_module_from_path


def test_split_by_speaker_merges_consecutive_lines(repo_root: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "text" / "transcript" / "python" / "split_by_speaker.py",
        "split_by_speaker_tool",
    )
    lines = [
        "[00:00:01] SPK_01: Първи ред\n",
        "[00:00:03] SPK_01: втори ред\n",
        "[00:00:05] SPK_02: друг говорител\n",
    ]

    combined, speakers, times, counts = module.parse_transcript(lines, normalize=True)

    assert len(combined) == 2
    assert speakers["SPK_1"] == ["[00:00:01] SPK_1: Първи ред втори ред"]
    assert times["SPK_1"] == ["00:00:01"]
    assert counts["SPK_1"] == 1
    assert counts["SPK_2"] == 1


def test_split_by_speaker_rejects_invalid_line(repo_root: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "text" / "transcript" / "python" / "split_by_speaker.py",
        "split_by_speaker_tool_invalid",
    )

    try:
        module.parse_transcript(["невалиден ред\n"])
    except ValueError as exc:
        assert "Невалиден формат" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid transcript line")


def test_extract_speakers_groups_blocks(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "text" / "transcript" / "python" / "extract_speakers.py",
        "extract_speakers_tool",
    )
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(
        "Иван Иванов — 00:00:01\n"
        "Здравей.\n"
        "Как си?\n\n"
        "Мария — 00:00:05\n"
        "Добре съм.\n",
        encoding="utf-8",
    )

    speakers = module.extract_speakers(transcript)

    assert speakers == {
        "Иван Иванов": ["[00:00:01] Здравей. Как си?"],
        "Мария": ["[00:00:05] Добре съм."],
    }
