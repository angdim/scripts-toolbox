# discogs_client/provider.py

"""
DiscogsProvider — имплементация на MetadataProvider интерфейса
за Discogs API клиента.

Този клас обединява:
- client.py
- search.py
- scoring.py
- trackmap.py
- chapters.py

и предоставя единен интерфейс към main.py.
"""

from typing import List, Dict, Any

from audio_metadata_normalizer.metadata_provider.interface import MetadataProvider

from .client import DiscogsClient
from .search import search_album
from .scoring import pick_best_release
from .trackmap import build_trackmap_with_chapters
from audio_metadata_normalizer.utils.chapters import (
    generate_ogm_chapter_file,
    embed_chapters_ffmpeg
)


class DiscogsProvider(MetadataProvider):
    """
    Discogs имплементация на MetadataProvider.
    """

    def __init__(self, user_token: str | None = None):
        self.client = DiscogsClient(user_token=user_token).client

    # ------------------------------------------------------------
    # 1) Търсене
    # ------------------------------------------------------------
    def search(self, artist: str, album: str) -> List[Any]:
        return search_album(self.client, artist, album)

    # ------------------------------------------------------------
    # 2) Избор на най-подходящ release
    # ------------------------------------------------------------
    def pick_best(self, results: List[Any], artist: str, album: str) -> Any:
        return pick_best_release(results, artist, album)

    # ------------------------------------------------------------
    # 3) Извличане на основни метаданни
    # ------------------------------------------------------------
    def extract_metadata(self, release: Any) -> Dict[str, Any]:
        """
        Връща:
        {
            "title": "...",
            "year": 1995,
            "country": "US",
            "label": "Integrity Music",
            "catno": "IMD14741",
            "cover_urls": [...],
            "genres": [...],
            "styles": [...]
        }
        """

        labels = [str(label) for label in getattr(release, "labels", [])]
        catno = release.data.get("catno")

        cover_urls = []
        for img in getattr(release, "images", []):
            if "uri" in img:
                cover_urls.append(img["uri"])

        return {
            "title": release.title,
            "year": getattr(release, "year", None),
            "country": getattr(release, "country", None),
            "label": labels[0] if labels else None,
            "catno": catno,
            "cover_urls": cover_urls,
            "genres": getattr(release, "genres", []),
            "styles": getattr(release, "styles", [])
        }

    # ------------------------------------------------------------
    # 4) Tracklist
    # ------------------------------------------------------------
    def extract_tracklist(self, release: Any) -> List[Dict[str, Any]]:
        """
        Връща:
        [
            {"title": "...", "duration": "07:19"},
            ...
        ]
        """
        tracklist = []
        for t in release.tracklist:
            tracklist.append({
                "title": t.title,
                "duration": t.duration
            })
        return tracklist

    # ------------------------------------------------------------
    # 5) Trackmap (seconds + timestamps)
    # ------------------------------------------------------------
    def build_trackmap(self, release: Any) -> List[Dict[str, Any]]:
        return build_trackmap_with_chapters(release)

    # ------------------------------------------------------------
    # 6) Генериране на chapter файл
    # ------------------------------------------------------------
    def generate_chapter_file(self, trackmap: List[Dict[str, Any]], output_path: str):
        generate_ogm_chapter_file(trackmap, output_path)

    # ------------------------------------------------------------
    # 7) Вграждане на chapters
    # ------------------------------------------------------------
    def embed_chapters(self, input_file: str, output_file: str, chapter_file: str):
        embed_chapters_ffmpeg(input_file, output_file, chapter_file)
