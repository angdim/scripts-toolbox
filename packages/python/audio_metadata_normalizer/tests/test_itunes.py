from audio_metadata_normalizer.itunes_client.provider import ITunesProvider
from audio_metadata_normalizer.itunes_client.scoring import (
    pick_best_release,
    score_release,
)
from audio_metadata_normalizer.itunes_client.trackmap import (
    build_trackmap_with_chapters,
)
from audio_metadata_normalizer.utils.provider_workflow import get_provider


ALBUM = {
    "wrapperType": "collection",
    "collectionType": "Album",
    "artistName": "Acappella",
    "collectionName": "Live from Paris",
    "collectionId": 64951216,
    "releaseDate": "2002-01-01T00:00:00Z",
    "trackCount": 14,
    "primaryGenreName": "Christian",
    "copyright": "℗ 2002 The Acappella Company",
    "country": "USA",
    "collectionViewUrl": "https://music.apple.com/us/album/live-from-paris/64951216?uo=4",
    "artworkUrl100": "https://example.test/cover.jpg",
}


TRACKS = [
    {
        "trackName": "Roll Jordon Roll",
        "trackNumber": 2,
        "trackTimeMillis": 311987,
    },
    {
        "trackName": "I Feel Good",
        "trackNumber": 1,
        "trackTimeMillis": 174720,
    },
]


class FakeITunesClient:
    def search_albums(self, artist, album):
        return [ALBUM]

    def lookup_album_tracks(self, collection_id):
        assert collection_id == 64951216
        return TRACKS


def test_score_release_rewards_matching_artist_and_album():
    assert score_release(ALBUM, "Acappella", "Live from Paris") > 100


def test_pick_best_release_returns_none_for_empty_results():
    assert pick_best_release([], "Acappella", "Live from Paris") is None


def test_trackmap_orders_tracks_and_computes_chapter_starts():
    assert build_trackmap_with_chapters(TRACKS) == [
        {
            "title": "I Feel Good",
            "duration": "02:55",
            "start": "00:00:00.000",
        },
        {
            "title": "Roll Jordon Roll",
            "duration": "05:12",
            "start": "00:02:55.000",
        },
    ]


def test_provider_extracts_metadata_and_trackmap_with_fake_client():
    provider = ITunesProvider()
    provider.client = FakeITunesClient()

    release = provider.search("Acappella", "Live from Paris")[0]
    meta = provider.extract_metadata(release)
    trackmap = provider.build_trackmap(release)

    assert meta["title"] == "Live from Paris"
    assert meta["year"] == "2002"
    assert meta["genres"] == ["Christian"]
    assert trackmap[0]["title"] == "I Feel Good"
    assert trackmap[1]["title"] == "Roll Jordon Roll"


def test_get_provider_accepts_itunes_source():
    assert isinstance(get_provider("itunes"), ITunesProvider)
