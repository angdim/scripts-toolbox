from audio_metadata_normalizer.utils import tagging
from audio_metadata_normalizer.utils.cover_profile import (
    ffmpeg_id3v2_version_for_profile,
    parse_cover_profile,
)


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


def test_lexus_cover_profile_selects_mp3_id3v23_only():
    assert ffmpeg_id3v2_version_for_profile("/tmp/album.mp3", "lexus-jpeg-500") == 3
    assert ffmpeg_id3v2_version_for_profile("/tmp/album.m4a", "lexus-jpeg-500") is None
    assert ffmpeg_id3v2_version_for_profile("/tmp/album.mp3", "source") is None


def test_parse_lexus_cover_profile():
    profile = parse_cover_profile("lexus-jpeg-300")

    assert profile.name == "lexus-jpeg-300"
    assert profile.output_format == "jpeg"
    assert profile.size == 300
    assert profile.lexus_safe is True


def test_tag_audio_file_uses_lexus_profile_for_mp3(monkeypatch, tmp_path):
    audio = tmp_path / "album.mp3"
    audio.write_bytes(b"audio")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")
    calls = []

    class FakePreparedCover:
        def __enter__(self):
            return str(cover)

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_prepared_cover_path(*args, **kwargs):
        return FakePreparedCover()

    def fake_ffmpeg_tag_file(*args, **kwargs):
        calls.append((args, kwargs))
        output_path = args[1]
        with open(output_path, "wb") as output:
            output.write(b"tagged")

    monkeypatch.setattr(tagging, "prepared_cover_path", fake_prepared_cover_path)
    monkeypatch.setattr(tagging, "ffmpeg_tag_file", fake_ffmpeg_tag_file)

    tagging.tag_audio_file(
        str(audio),
        {"title": "Album"},
        str(cover),
        dry_run=False,
        cover_profile="lexus-jpeg-500",
    )

    assert calls[0][1]["id3v2_version"] == 3
    assert audio.read_bytes() == b"tagged"
