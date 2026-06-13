# audio_metadata_normalizer/utils/provider_workflow.py

"""
Общ workflow около metadata provider-и.

Тук е логиката за:
- избор на provider;
- търсене и избор на най-добър релийз;
- извличане на metadata и trackmap;
- подготвяне на artist/album контекст;
- matching между локални файлове и trackmap за команда.
"""

from audio_metadata_normalizer.discogs_client.provider import DiscogsProvider
from audio_metadata_normalizer.itunes_client.provider import ITunesProvider
from audio_metadata_normalizer.mb_client.provider import MusicBrainzProvider
from audio_metadata_normalizer.utils.album import (
    resolve_artist_album,
    validate_track_count,
)
from audio_metadata_normalizer.utils.files import iter_audio_files
from audio_metadata_normalizer.utils.matching import match_files_to_tracks


def get_provider(source: str):
    source = source.lower()

    if source == "discogs":
        return DiscogsProvider()

    if source == "musicbrainz":
        return MusicBrainzProvider()

    if source == "itunes":
        return ITunesProvider()

    raise ValueError(f"Непознат източник на метаданни: {source}")


def find_best_release(provider, artist: str, album: str):
    results = provider.search(artist, album)
    if not results:
        print("Няма намерени релийзи.")
        return None

    best = provider.pick_best(results, artist, album)
    if not best:
        print("Няма подходящ релийз.")
        return None

    return best


def build_release_data(provider, release):
    return provider.extract_metadata(release), provider.build_trackmap(release)


def resolve_album_context(album_dir: str, args):
    artist, album = resolve_artist_album(album_dir, args.artist, args.album)

    if not artist or not album:
        print(f"Неуспешно извличане на artist/album за: {album_dir}")
        print("Подай ги ръчно с --artist и --album.")
        return None

    return artist, album


def print_album_header(action: str | None, artist: str, album: str):
    if action:
        print(f"\n=== {action}: {artist} - {album} ===")
        return

    print(f"\n=== {artist} - {album} ===")


def load_album_release_data(provider, artist: str, album: str):
    best = find_best_release(provider, artist, album)
    if not best:
        return None

    return build_release_data(provider, best)


def match_album_tracks_for_command(
        album_dir: str,
        trackmap,
        min_score: float,
        operation_label: str
):
    files = list(iter_audio_files(album_dir))
    if not validate_track_count(files, trackmap):
        return None

    matched = match_files_to_tracks(files, trackmap, min_score)
    if not matched:
        print(f"{operation_label} е прекъснато заради неясно "
              "съвпадение между файлове и тракове.")
        return None

    return matched
