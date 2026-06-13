from audio_metadata_normalizer.mb_client.scoring import pick_best_release, score_release


def test_score_release_rewards_matching_artist_album_and_album_type():
    release = {
        "title": "No Compromise",
        "artist-credit": [{"artist": {"name": "Keith Green"}}],
        "medium-list": [{"format": "CD"}],
        "date": "1978-01-01",
        "country": "US",
        "release-group": {"primary-type": "Album"},
    }

    assert score_release(release, "Keith Green", "No Compromise") > 100


def test_pick_best_release_returns_none_for_empty_results():
    assert pick_best_release([], "Keith Green", "No Compromise") is None


def test_pick_best_release_returns_highest_scored_release():
    wrong = {
        "title": "Other Album",
        "artist-credit": [{"artist": {"name": "Other Artist"}}],
    }
    right = {
        "title": "No Compromise",
        "artist-credit": [{"artist": {"name": "Keith Green"}}],
        "release-group": {"primary-type": "Album"},
    }

    assert pick_best_release([wrong, right], "Keith Green", "No Compromise") is right
