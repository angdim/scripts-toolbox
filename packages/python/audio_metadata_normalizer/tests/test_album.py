from audio_metadata_normalizer.utils.album import (
    filter_album_dirs,
    guess_artist_album_from_dir,
    parse_album_directory_name,
)


def test_guess_artist_album_removes_year_and_quality_tags():
    assert guess_artist_album_from_dir(
        "/music/Acappella/Acappella - Classycal (1994) [320 kbps]"
    ) == ("Acappella", "Classycal")


def test_guess_artist_album_handles_year_before_album_title():
    assert guess_artist_album_from_dir(
        "/music/Acappella/Acappella - (2002) Live from Paris"
    ) == ("Acappella", "Live from Paris")


def test_guess_artist_album_uses_parent_artist_when_name_starts_with_year():
    assert guess_artist_album_from_dir(
        "/music/Acappella/1994 - Classycal"
    ) == ("Acappella", "Classycal")


def test_guess_artist_album_uses_parent_artist_for_compact_year_prefix():
    assert guess_artist_album_from_dir(
        "/music/Acappella/1994-Classycal"
    ) == ("Acappella", "Classycal")


def test_guess_artist_album_handles_artist_compact_year_prefix():
    assert guess_artist_album_from_dir(
        "/music/Acappella/Acappella - 1994-Classycal"
    ) == ("Acappella", "Classycal")


def test_guess_artist_album_keeps_year_when_it_is_the_album_title():
    assert guess_artist_album_from_dir(
        "/music/Van Halen/Van Halen - 1984"
    ) == ("Van Halen", "1984")


def test_parse_album_directory_name_exposes_year_separately():
    parsed = parse_album_directory_name(
        "Acappella - Classycal (1994) [320 kbps]",
        "Acappella",
    )

    assert parsed.artist == "Acappella"
    assert parsed.album == "Classycal"
    assert parsed.year == "1994"


def test_filter_album_dirs_matches_parsed_album_name():
    album_dirs = [
        "/music/Acappella/Acappella - Classycal (1994) [320 kbps]",
        "/music/Acappella/Acappella - (2002) Live from Paris",
    ]

    assert filter_album_dirs(album_dirs, ["Classycal"]) == [album_dirs[0]]
