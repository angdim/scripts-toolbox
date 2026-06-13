from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from tests.helpers.importing import import_module_from_path
from tests.helpers.media_factory import make_test_mp4

pytestmark = [pytest.mark.unit, pytest.mark.media]


def test_split_media_time_helpers(repo_root: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "split_media_by_time.py",
        "split_media_by_time_tool",
    )

    assert module.format_time(0) == "00:00:00"
    assert module.format_time(3661) == "01:01:01"


def test_video4lexus_needs_scaling(repo_root: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "video4lexus.py",
        "video4lexus_tool",
    )

    assert module.needs_scaling(1280, 720) is True
    assert module.needs_scaling(640, 360) is False


def test_video4lexus_reads_generated_video_info(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "video4lexus.py",
        "video4lexus_info",
    )
    video = make_test_mp4(tmp_path / "input.mp4", duration=0.3)

    info = module.get_video_info(video)

    assert info is not None
    assert info["width"] == 160
    assert info["height"] == 120
    assert info["sample_rate"] > 0


def test_video4lexus_v2_dimensions(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "video4lexus_v2.py",
        "video4lexus_v2_tool",
    )
    video = make_test_mp4(tmp_path / "input.mp4", duration=0.3)

    assert module.get_video_dimensions(video) == (160, 120)


def test_video4lexus_v3_encoding_strategy(repo_root: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "video4lexus_v3.py",
        "video4lexus_v3_tool",
    )

    keep = module.calculate_encoding_strategy({"width": 640, "height": 360, "dar_decimal": 16 / 9})
    assert keep[0] == "keep"

    direct = module.calculate_encoding_strategy({"width": 1000, "height": 900, "dar_decimal": 4 / 3})
    assert direct[0] == "direct"
    assert direct[1] <= module.MAX_WIDTH
    assert direct[2] <= module.MAX_HEIGHT

    wide = module.calculate_encoding_strategy({"width": 1920, "height": 1080, "dar_decimal": 16 / 9})
    assert wide[0] == "anamorphic"


def test_video4lexus_v3_reads_generated_video(repo_root: Path, tmp_path: Path) -> None:
    module = import_module_from_path(
        repo_root / "tools" / "media" / "video" / "python" / "video4lexus_v3.py",
        "video4lexus_v3_info",
    )
    video = make_test_mp4(tmp_path / "input.mp4", duration=0.3)

    info = module.get_video_info(video)

    assert info is not None
    assert info["width"] == 160
    assert info["height"] == 120
    assert isinstance(info["dar"], Fraction)
