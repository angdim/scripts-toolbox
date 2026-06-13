from audio_metadata_normalizer.discogs_client.scoring import pick_best_release


class FakeDiscogsRelease:
    def __init__(self, title, formats=None, country=None, year=None):
        self.title = title
        self.formats = formats or []
        self.country = country
        self.year = year
        self.labels = []


def test_pick_best_release_prefers_matching_artist_album():
    wrong = FakeDiscogsRelease("Other Artist - Other Album")
    right = FakeDiscogsRelease(
        "Keith Green - No Compromise",
        formats=[{"name": "CD", "descriptions": ["Album"]}],
        country="US",
        year=1978,
    )

    assert pick_best_release([wrong, right], "Keith Green", "No Compromise") is right
