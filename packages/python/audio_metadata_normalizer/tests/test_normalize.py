from audio_metadata_normalizer.utils.normalize import (
    build_track_filename,
    natural_sort_key,
    normalize,
    normalize_track_filename,
)


def test_normalize_text():
    assert normalize("NO_COMPROMISE") == "no compromise"
    assert normalize("No   Compromise!!!") == "no compromise!!!"
    assert normalize("01 - Soften Your Heart.mp3") == "01 - soften your heart mp3"


def test_normalize_track_filename_removes_track_prefix_and_youtube_noise():
    assert normalize_track_filename("01 - Soften Your Heart.mp3") == "soften your heart"
    assert normalize_track_filename("02. You Put This Love In My Heart.flac") == "you put this love in my heart"
    assert normalize_track_filename("01-Soften Your Heart [Official Audio].flac") == "soften your heart"


def test_build_track_filename_uses_total_track_padding():
    assert build_track_filename(1, "Song (Official Video)", ".flac", 14) == "01-Song.flac"
    assert build_track_filename(9, "Finale", ".mp3", 9) == "9-Finale.mp3"
    assert build_track_filename(
        1,
        "Joyful, Joyful We Adore Thee",
        ".mp3",
        10,
    ) == "01-Joyful, Joyful We Adore Thee.mp3"
    assert build_track_filename(
        2,
        "Question: Answer / Unsafe?",
        ".flac",
        10,
    ) == "02-Question Answer Unsafe.flac"


def test_natural_sort_key_handles_mixed_number_positions():
    names = [
        "Acappella - Classycal (1994) [320 kbps]",
        "10.flac",
        "2.flac",
        "01.flac",
    ]

    assert sorted(names, key=natural_sort_key) == [
        "01.flac",
        "2.flac",
        "10.flac",
        "Acappella - Classycal (1994) [320 kbps]",
    ]
