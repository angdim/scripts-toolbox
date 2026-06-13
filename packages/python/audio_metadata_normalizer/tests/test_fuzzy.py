from audio_metadata_normalizer.mb_client.fuzzy import (
    match_track,
    pick_best_release,
    pick_best_release_group,
)


def test_pick_best_release_group_uses_title_similarity():
    groups = [
        {"id": "wrong", "title": "Songs for the Shepherd"},
        {"id": "right", "title": "No Compromise"},
    ]

    assert pick_best_release_group("No Compromise", groups)["id"] == "right"


def test_pick_best_release_uses_title_similarity():
    releases = [
        {"id": "wrong", "title": "So You Wanna Go Back to Egypt"},
        {"id": "right", "title": "No Compromise"},
    ]

    assert pick_best_release(releases, "No Compromise")["id"] == "right"


def test_match_track_strips_local_prefix_and_youtube_noise():
    tracks = [
        {"recording": {"title": "Soften Your Heart"}},
        {"recording": {"title": "You Put This Love In My Heart"}},
    ]

    match = match_track("01-Soften Your Heart [Official Audio].flac", tracks)

    assert match["recording"]["title"] == "Soften Your Heart"
