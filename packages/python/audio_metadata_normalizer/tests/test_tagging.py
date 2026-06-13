from audio_metadata_normalizer.utils import tagging


def test_build_track_tags_includes_album_and_track_number():
    meta = {
        "title": "No Compromise",
        "year": "1978",
        "genres": ["Rock", "Gospel"],
        "label": "Sparrow",
        "catno": "SPR-1024",
    }
    track = {"title": "Soften Your Heart"}

    assert tagging.build_track_tags(meta, track, "Keith Green", 1, 14) == {
        "title": "Soften Your Heart",
        "album": "No Compromise",
        "artist": "Keith Green",
        "album_artist": "Keith Green",
        "track": "1/14",
        "date": "1978",
        "genre": "Rock, Gospel",
        "comment": "Sparrow SPR-1024",
    }


def test_build_temp_tag_path_preserves_audio_extension():
    assert (
        tagging.build_temp_tag_path("/tmp/Album/01-Soften.flac", 1)
        == "/tmp/Album/.tmp_tag_1_01-Soften.flac"
    )


def test_tag_audio_file_dry_run_does_not_call_ffmpeg(monkeypatch):
    called = False

    def fake_ffmpeg_tag_file(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(tagging, "ffmpeg_tag_file", fake_ffmpeg_tag_file)

    tagging.tag_audio_file("/tmp/Album/album.flac", {"title": "Album"}, None, dry_run=True)

    assert called is False
