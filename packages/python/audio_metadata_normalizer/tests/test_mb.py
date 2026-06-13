from audio_metadata_normalizer.mb_client.client import MBClient


def test_mb_client_search_releases_uses_musicbrainzngs(monkeypatch):
    captured = {}

    def fake_set_useragent(app, version, contact):
        captured["useragent"] = (app, version, contact)

    def fake_search_releases(**kwargs):
        captured["search"] = kwargs
        return {"release-list": [{"id": "release-1"}]}

    monkeypatch.setattr(
        "audio_metadata_normalizer.mb_client.client.musicbrainzngs.set_useragent",
        fake_set_useragent,
    )
    monkeypatch.setattr(
        "audio_metadata_normalizer.mb_client.client.musicbrainzngs.search_releases",
        fake_search_releases,
    )

    client = MBClient(user_agent="TestApp", contact="test@example.com")
    result = client.search_releases("Keith Green", "No Compromise")

    assert captured["useragent"] == ("TestApp", "1.0", "test@example.com")
    assert captured["search"]["artist"] == "Keith Green"
    assert captured["search"]["release"] == "No Compromise"
    assert result == [{"id": "release-1"}]


def test_mb_client_get_release_returns_release_dict(monkeypatch):
    def fake_get_release_by_id(mbid, includes):
        return {"release": {"id": mbid, "includes": includes}}

    monkeypatch.setattr(
        "audio_metadata_normalizer.mb_client.client.musicbrainzngs.set_useragent",
        lambda *args: None,
    )
    monkeypatch.setattr(
        "audio_metadata_normalizer.mb_client.client.musicbrainzngs.get_release_by_id",
        fake_get_release_by_id,
    )

    client = MBClient()
    result = client.get_release("release-1")

    assert result["id"] == "release-1"
    assert "recordings" in result["includes"]
