from audio_metadata_normalizer.mb_client.trackmap import (
    build_trackmap_with_chapters,
    duration_to_seconds,
    seconds_to_timestamp,
)


def test_duration_to_seconds_handles_mm_ss():
    assert duration_to_seconds("04:12") == 252
    assert duration_to_seconds("") is None


def test_seconds_to_timestamp_uses_chapter_format():
    assert seconds_to_timestamp(252) == "00:04:12.000"


def test_build_trackmap_with_chapters_combines_titles_durations_and_starts():
    release = {
        "media": [
            {
                "tracks": [
                    {"title": "Soften Your Heart", "length": 252000},
                    {"title": "You Put This Love In My Heart", "length": 189000},
                ]
            }
        ]
    }

    assert build_trackmap_with_chapters(release) == [
        {
            "title": "Soften Your Heart",
            "duration": "04:12",
            "start": "00:00:00.000",
        },
        {
            "title": "You Put This Love In My Heart",
            "duration": "03:09",
            "start": "00:04:12.000",
        },
    ]
