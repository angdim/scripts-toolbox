import os

from audio_metadata_normalizer.utils.dir_rename import (
    album_dir_release_is_safe_match,
    apply_dir_rename_plan,
    build_album_dir_name,
    build_album_dir_rename_plan,
    dir_rename_plan_has_conflicts,
)


META = {
    "title": "Live from Paris",
    "year": "2002",
}


def test_build_album_dir_name_supports_year_title_template():
    assert build_album_dir_name(META, "Acappella", "year-title") == "2002-Live from Paris"


def test_build_album_dir_name_supports_artist_year_title_template():
    assert (
        build_album_dir_name(META, "Acappella", "artist-year-title")
        == "Acappella - 2002-Live from Paris"
    )


def test_build_album_dir_name_returns_none_without_year():
    assert build_album_dir_name({"title": "Album"}, "Artist", "year-title") is None


def test_build_album_dir_rename_plan_uses_same_parent_dir():
    assert build_album_dir_rename_plan(
        "/music/Acappella/Old Name",
        META,
        "Acappella",
        "year-title",
    ) == (
        "/music/Acappella/Old Name",
        "/music/Acappella/2002-Live from Paris",
    )


def test_dir_rename_plan_detects_duplicate_targets():
    plan = [
        ("/music/a", "/music/2002-Album"),
        ("/music/b", "/music/2002-Album"),
    ]

    assert dir_rename_plan_has_conflicts(plan) is True


def test_apply_dir_rename_plan_renames_directory(tmp_path):
    source = tmp_path / "Old Album"
    source.mkdir()
    target = tmp_path / "2002-Live from Paris"

    apply_dir_rename_plan([(str(source), str(target))], dry_run=False)

    assert not source.exists()
    assert target.is_dir()


def test_apply_dir_rename_plan_dry_run_does_not_rename(tmp_path):
    source = tmp_path / "Old Album"
    source.mkdir()
    target = tmp_path / "2002-Live from Paris"

    apply_dir_rename_plan([(str(source), str(target))], dry_run=True)

    assert source.is_dir()
    assert not os.path.exists(target)


def test_album_dir_release_is_safe_match_rejects_low_title_similarity():
    assert album_dir_release_is_safe_match(
        "/music/Hosanna Music/Hosanna Music - 1992 - Acapella",
        "Acapella",
        {"title": "Jerusalem Arise (Live)", "year": "2010"},
        0.75,
    ) is False


def test_album_dir_release_is_safe_match_rejects_year_mismatch():
    assert album_dir_release_is_safe_match(
        "/music/Glad/Glad - The Acappella Project III [Special Edition] (2004)",
        "The Acappella Project III",
        {"title": "The Acappella Project III", "year": "1996"},
        0.75,
    ) is False


def test_album_dir_release_is_safe_match_accepts_close_title():
    assert album_dir_release_is_safe_match(
        "/music/Glad/Glad - 1990 - The Acappella Project II",
        "The Acappella Project II",
        {"title": "The a Capella Project II", "year": "1990"},
        0.75,
    ) is True
