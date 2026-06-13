# metadata_provider/interface.py

from abc import ABC, abstractmethod
from typing import Any, List, Dict


class MetadataProvider(ABC):
    """
    Абстрактен интерфейс за всички метаданни клиенти:
    - Discogs
    - MusicBrainz
    - бъдещи API клиенти

    Всеки клиент трябва да имплементира тези методи.
    """

    @abstractmethod
    def search(self, artist: str, album: str) -> List[Any]:
        """Търси релийзи по artist + album."""
        pass

    @abstractmethod
    def pick_best(self, results: List[Any], artist: str, album: str) -> Any:
        """Избира най-подходящия release."""
        pass

    @abstractmethod
    def extract_metadata(self, release: Any) -> Dict[str, Any]:
        """Извлича основни метаданни: title, year, country, label, catno."""
        pass

    @abstractmethod
    def extract_tracklist(self, release: Any) -> List[Dict[str, Any]]:
        """Извлича tracklist + durations."""
        pass

    @abstractmethod
    def build_trackmap(self, release: Any) -> List[Dict[str, Any]]:
        """Генерира trackmap със seconds + timestamps."""
        pass

    @abstractmethod
    def generate_chapter_file(self, trackmap: List[Dict[str, Any]], output_path: str):
        """Генерира OGM chapter файл."""
        pass

    @abstractmethod
    def embed_chapters(self, input_file: str, output_file: str, chapter_file: str):
        """Вгражда chapters в аудио файл."""
        pass
