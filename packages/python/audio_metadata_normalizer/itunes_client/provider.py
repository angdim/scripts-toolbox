# audio_metadata_normalizer/itunes_client/provider.py

"""iTunesProvider — MetadataProvider имплементация за iTunes Search API."""

from typing import Any

from audio_metadata_normalizer.metadata_provider.interface import MetadataProvider
from audio_metadata_normalizer.utils.chapters import (
    embed_chapters_ffmpeg,
    generate_ogm_chapter_file,
)

from .client import ITunesClient
from .scoring import pick_best_release
from .search import search_album
from .trackmap import build_trackmap_with_chapters


class ITunesProvider(MetadataProvider):
    def __init__(self, country: str = "US"):
        self.client = ITunesClient(country=country)

    def search(self, artist: str, album: str) -> list[Any]:
        return search_album(self.client, artist, album)

    def pick_best(self, results: list[Any], artist: str, album: str) -> Any:
        return pick_best_release(results, artist, album)

    def _tracks_for_release(self, release: dict[str, Any]) -> list[dict[str, Any]]:
        if "_tracks" not in release:
            release["_tracks"] = self.client.lookup_album_tracks(release["collectionId"])
        return release["_tracks"]

    def extract_metadata(self, release: dict[str, Any]) -> dict[str, Any]:
        release_date = release.get("releaseDate") or ""
        year = release_date[:4] if len(release_date) >= 4 else None
        genre = release.get("primaryGenreName")

        return {
            "title": release.get("collectionName"),
            "year": year,
            "country": release.get("country"),
            "label": release.get("copyright"),
            "catno": None,
            "cover_urls": [
                release["artworkUrl100"]
            ] if release.get("artworkUrl100") else [],
            "genres": [genre] if genre else [],
            "styles": [],
            "source_url": release.get("collectionViewUrl"),
            "source": "iTunes",
        }

    def extract_tracklist(self, release: dict[str, Any]) -> list[dict[str, Any]]:
        tracks = self._tracks_for_release(release)
        return [
            {
                "title": track.get("trackName"),
                "duration": track.get("trackTimeMillis"),
            }
            for track in sorted(tracks, key=lambda item: item.get("trackNumber") or 0)
        ]

    def build_trackmap(self, release: dict[str, Any]) -> list[dict[str, Any]]:
        return build_trackmap_with_chapters(self._tracks_for_release(release))

    def generate_chapter_file(self, trackmap: list[dict[str, Any]], output_path: str):
        generate_ogm_chapter_file(trackmap, output_path)

    def embed_chapters(self, input_file: str, output_file: str, chapter_file: str):
        embed_chapters_ffmpeg(input_file, output_file, chapter_file)
