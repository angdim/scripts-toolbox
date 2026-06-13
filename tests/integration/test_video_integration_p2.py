from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.importing import import_module_from_path
from tests.helpers.media_factory import make_test_mp4
from tests.helpers.script_runner import run_command

pytestmark = [pytest.mark.integration, pytest.mark.media, pytest.mark.linux]


def test_python_split_media_by_time_creates_parts(repo_root: Path, tmp_path: Path, monkeypatch) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "split_media_by_time.py",
        "split_media_by_time_integration",
    )
    video = make_test_mp4(tmp_path / "input.mp4", duration=1.2)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "CHUNK_DURATION", 1)
    monkeypatch.setattr(module, "OVERLAP", 0)

    module.split_media(str(video))

    assert (tmp_path / "part_01.mp4").exists()
    assert (tmp_path / "part_02.mp4").exists()


def test_bash_split_media_by_time_creates_part(repo_root: Path, tmp_path: Path) -> None:
    video = make_test_mp4(tmp_path / "input.mp4", duration=1.2)
    script = repo_root / "tools" / "media" / "video" / "bash" / "split_media_by_time.sh"

    result = run_command(["bash", script, video], cwd=tmp_path, timeout=120, check=True)

    assert "Готово" in result.stdout
    assert (tmp_path / "part_01.mp4").exists()


def test_video4lexus_v2_converts_generated_video(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "video4lexus_v2.py",
        "video4lexus_v2_integration",
    )
    video = make_test_mp4(tmp_path / "input.mp4", duration=0.3)
    output = tmp_path / "out.mp4"

    assert module.convert_video(video, output) is True
    assert output.exists()
    assert output.stat().st_size > 0
