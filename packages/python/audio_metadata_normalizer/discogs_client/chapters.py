# audio_metadata_normalizer/discogs_client/chapters.py

"""
Съвместим wrapper за chapter функциите на Discogs.

Реалната имплементация е обща и се намира в
audio_metadata_normalizer.utils.chapters.
"""

from audio_metadata_normalizer.utils.chapters import (
    embed_chapters_ffmpeg,
    generate_ogm_chapter_file,
    parse_ogm_chapter_file,
)

__all__ = [
    "embed_chapters_ffmpeg",
    "generate_ogm_chapter_file",
    "parse_ogm_chapter_file",
]
