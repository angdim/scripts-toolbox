# mb_client/provider.py

"""
MusicBrainzProvider — имплементация на MetadataProvider интерфейса
за MusicBrainz API клиента.

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

from .client import MBClient
from .search import search_album
from .scoring import pick_best_release
from .trackmap import build_trackmap_with_chapters
from audio_metadata_normalizer.utils.chapters import (
    generate_ogm_chapter_file,
    embed_chapters_ffmpeg
)
from audio_metadata_normalizer.utils.normalize import normalize_duration_ms


class MusicBrainzProvider(MetadataProvider):
    """
    MusicBrainz имплементация на MetadataProvider.
    """

    def __init__(self, user_agent: str | None = None, contact: str | None = None):
        self.client = MBClient(user_agent=user_agent, contact=contact)

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
            "label": "...",
            "catno": "...",
            "cover_urls": [...],
            "genres": [...],
            "styles": []
        }
        """

        # Извличане на обложки
        cover_urls = []
        if "cover-art-archive" in release:
            if release["cover-art-archive"].get("front"):
                cover_urls.append(
                    f"https://coverartarchive.org/release/{release['id']}/front"
                )

        # Лейбъл и каталожен номер
        label = None
        catno = None
        if "label-info" in release:
            info = release["label-info"]
            if info:
                li = info[0]
                if "label" in li:
                    label = li["label"]["name"]
                catno = li.get("catalog-number")

        # Година
        year = None
        if "date" in release and release["date"]:
            year = release["date"][:4]

        return {
            "title": release.get("title"),
            "year": year,
            "country": release.get("country"),
            "label": label,
            "catno": catno,
            "cover_urls": cover_urls,
            "genres": release.get("genres", []),
            "styles": []  # MB няма styles
        }

    # ------------------------------------------------------------
    # 4) Tracklist
    # ------------------------------------------------------------
    def extract_tracklist(self, release: Any) -> List[Dict[str, Any]]:
        """
        Връща:
        [
            {"title": "...", "duration": "03:12"},
            ...
        ]
        """

        tracklist = []

        for medium in release.get("media", []):
            for t in medium.get("tracks", []):
                ms = t.get("length")
                duration = normalize_duration_ms(ms)

                tracklist.append({
                    "title": t.get("title"),
                    "duration": duration
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
