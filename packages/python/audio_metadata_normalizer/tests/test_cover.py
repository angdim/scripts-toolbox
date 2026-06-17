from io import BytesIO

from PIL import Image

from audio_metadata_normalizer.utils.cover import (
    build_cover_output_path,
    download_cover,
    find_existing_cover,
    inspect_image_file,
    resolve_cover_path,
    select_cover_url,
)


def make_image_bytes(image_format="JPEG", size=(32, 24)):
    buffer = BytesIO()
    Image.new("RGB", size, color=(200, 20, 20)).save(buffer, format=image_format)
    return buffer.getvalue()


def test_find_existing_cover_uses_known_names(tmp_path):
    cover = tmp_path / "folder.jpg"
    cover.write_bytes(b"cover")

    assert find_existing_cover(str(tmp_path)) == str(cover)


def test_find_existing_cover_uses_single_album_named_image(tmp_path):
    cover = tmp_path / "God_Is_Able.jpg"
    cover.write_bytes(b"cover")

    assert find_existing_cover(str(tmp_path)) == str(cover)


def test_find_existing_cover_ignores_ambiguous_album_named_images(tmp_path):
    first = tmp_path / "God_Is_Able.jpg"
    second = tmp_path / "Back_Cover.jpg"
    first.write_bytes(b"cover")
    second.write_bytes(b"cover")

    assert find_existing_cover(str(tmp_path)) is None


def test_resolve_cover_path_prefers_explicit_cover(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")

    assert (
        resolve_cover_path(str(tmp_path), "/manual/front.jpg", auto_cover=True)
        == "/manual/front.jpg"
    )


def test_resolve_cover_path_makes_relative_explicit_cover_album_relative(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")

    assert resolve_cover_path(str(tmp_path), "cover.jpg", auto_cover=True) == str(cover)


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


def test_select_cover_url_uses_one_based_index():
    meta = {"cover_urls": ["https://example.test/a.jpg", "https://example.test/b.jpg"]}

    assert select_cover_url(meta, 2) == "https://example.test/b.jpg"
    assert select_cover_url(meta, 3) is None


def test_build_cover_output_path_defaults_to_cover_jpg(tmp_path):
    assert (
        build_cover_output_path(str(tmp_path), "https://example.test/image")
        == str(tmp_path / "cover.jpg")
    )


def test_build_cover_output_path_uses_safe_album_title(tmp_path):
    assert (
        build_cover_output_path(
            str(tmp_path),
            "https://example.test/cover.jpeg",
            album_title="God Is Able",
        )
        == str(tmp_path / "God_Is_Able.jpg")
    )


def test_build_cover_output_path_preserves_non_jpeg_extension(tmp_path):
    assert (
        build_cover_output_path(
            str(tmp_path),
            "https://example.test/cover.png",
            album_title="God Is Able",
        )
        == str(tmp_path / "God_Is_Able.png")
    )


def test_inspect_image_file_reports_format_dimensions_and_size(tmp_path):
    cover = tmp_path / "God_Is_Able.jpg"
    data = make_image_bytes(size=(64, 48))
    cover.write_bytes(data)

    info = inspect_image_file(str(cover), label="local #1")

    assert info.label == "local #1"
    assert info.image_format == "JPEG"
    assert info.width == 64
    assert info.height == 48
    assert info.size_bytes == len(data)


def test_ensure_cover_download_dry_run_reports_local_and_remote(monkeypatch, tmp_path, capsys):
    local = tmp_path / "God_Is_Able.jpg"
    local.write_bytes(make_image_bytes(size=(50, 50)))
    remote_data = make_image_bytes(size=(300, 300))
    meta = {
        "title": "God Is Able",
        "cover_urls": [
            "https://example.test/front.jpg",
            "https://example.test/back.jpg",
        ],
    }

    monkeypatch.setattr(
        "audio_metadata_normalizer.utils.cover.fetch_remote_cover_bytes",
        lambda url: remote_data,
    )

    from audio_metadata_normalizer.utils.cover import ensure_cover_download

    assert ensure_cover_download(str(tmp_path), meta, dry_run=True) is None
    output = capsys.readouterr().out

    assert "Локални обложки:" in output
    assert "local #1" in output
    assert "50x50px" in output
    assert "Remote обложки:" in output
    assert "remote #1" in output
    assert "remote #2" in output
    assert "300x300px" in output
    assert "--cover-index N" in output


def test_download_cover_uses_browser_like_headers(monkeypatch, tmp_path):
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"image"

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    output = tmp_path / "cover.jpg"
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert download_cover("https://example.test/cover.jpg", str(output)) == str(output)
    assert output.read_bytes() == b"image"
    assert calls[0][0].headers["User-agent"].startswith("Mozilla/5.0")
    assert "image/" in calls[0][0].headers["Accept"]
    assert calls[0][1] == 30
