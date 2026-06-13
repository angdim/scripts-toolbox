from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.script_runner import run_command

pytestmark = [pytest.mark.integration, pytest.mark.linux]


def test_generate_playlist_uses_relative_paths(repo_root: Path, tmp_path: Path) -> None:
    media = tmp_path / "media"
    nested = media / "Албуми" / "A"
    nested.mkdir(parents=True)
    (nested / "song one.mp3").write_text("fake", encoding="utf-8")
    (nested / "video one.mp4").write_text("fake", encoding="utf-8")
    (nested / "ignore.txt").write_text("fake", encoding="utf-8")

    script = repo_root / "tools" / "media" / "audio" / "bash" / "generate_playlist.sh"
    run_command(["bash", script, media], cwd=repo_root, check=True)

    playlist = media / "playlist.m3u8"
    content = playlist.read_text(encoding="utf-8")
    assert content.startswith("#EXTM3U")
    assert "Албуми/A/song one.mp3" in content
    assert "Албуми/A/video one.mp4" in content
    assert str(media) not in content
    assert "ignore.txt" not in content


def test_generate_playlist_audio_only_and_master(repo_root: Path, tmp_path: Path) -> None:
    media = tmp_path / "media"
    (media / "one").mkdir(parents=True)
    (media / "two").mkdir()
    (media / "one" / "a.mp3").write_text("fake", encoding="utf-8")
    (media / "one" / "a.mp4").write_text("fake", encoding="utf-8")
    (media / "two" / "b.flac").write_text("fake", encoding="utf-8")

    script = repo_root / "tools" / "media" / "audio" / "bash" / "generate_playlist.sh"
    run_command(["bash", script, "--audio-only", "--group", "--master", media], cwd=repo_root, check=True)

    master = media / "master_playlist.m3u8"
    assert master.exists()
    assert "one/playlist.m3u8" in master.read_text(encoding="utf-8")
    assert "two/playlist.m3u8" in master.read_text(encoding="utf-8")
    assert "a.mp4" not in (media / "one" / "playlist.m3u8").read_text(encoding="utf-8")
