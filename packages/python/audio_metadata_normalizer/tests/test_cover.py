from audio_metadata_normalizer.utils.cover import (
    build_cover_output_path,
    find_existing_cover,
    resolve_cover_path,
    select_cover_url,
)


def test_find_existing_cover_uses_known_names(tmp_path):
    cover = tmp_path / "folder.jpg"
    cover.write_bytes(b"cover")

    assert find_existing_cover(str(tmp_path)) == str(cover)


def test_resolve_cover_path_prefers_explicit_cover(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")

    assert (
        resolve_cover_path(str(tmp_path), "/manual/front.jpg", auto_cover=True)
        == "/manual/front.jpg"
    )


def test_resolve_cover_path_uses_local_cover_when_auto_cover_is_enabled(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")

    assert resolve_cover_path(str(tmp_path), None, auto_cover=True) == str(cover)


def test_resolve_cover_path_returns_none_without_auto_cover(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")

    assert resolve_cover_path(str(tmp_path), None, auto_cover=False) is None


def test_select_cover_url_returns_first_url():
    assert select_cover_url({"cover_urls": ["https://example.test/a.jpg"]}) == "https://example.test/a.jpg"


def test_build_cover_output_path_defaults_to_cover_jpg(tmp_path):
    assert (
        build_cover_output_path(str(tmp_path), "https://example.test/image")
        == str(tmp_path / "cover.jpg")
    )
