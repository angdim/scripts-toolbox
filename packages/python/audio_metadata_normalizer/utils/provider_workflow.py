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

from __future__ import annotations

import socket
from urllib.error import HTTPError, URLError

import discogs_client.exceptions
import musicbrainzngs

from audio_metadata_normalizer.discogs_client.provider import DiscogsProvider
from audio_metadata_normalizer.itunes_client.provider import ITunesProvider
from audio_metadata_normalizer.mb_client.provider import MusicBrainzProvider
from audio_metadata_normalizer.utils.album import (
    resolve_artist_album_from_audio_file,
    resolve_artist_album,
    validate_track_count,
)
from audio_metadata_normalizer.utils.files import iter_audio_files
from audio_metadata_normalizer.utils.matching import match_files_to_tracks

PROVIDER_REQUEST_ERRORS = (
    TimeoutError,
    socket.gaierror,
    HTTPError,
    URLError,
    discogs_client.exceptions.DiscogsAPIError,
    musicbrainzngs.NetworkError,
    musicbrainzngs.ResponseError,
    musicbrainzngs.WebServiceError,
)


def get_provider(source: str):
    source = source.lower()

    if source == "discogs":
        return DiscogsProvider()

    if source == "musicbrainz":
        return MusicBrainzProvider()

    if source == "itunes":
        return ITunesProvider()

    raise ValueError(f"Непознат източник на метаданни: {source}")


def _provider_name(provider) -> str:
    name = provider.__class__.__name__
    return name.replace("Provider", "") or name


def _format_provider_error(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"

    reason = getattr(exc, "reason", None)
    if reason:
        return str(reason)

    return str(exc)


def print_provider_request_error(provider, exc: Exception, action: str) -> None:
    print(f"Грешка при {action} чрез {_provider_name(provider)}: {_format_provider_error(exc)}")
    print("Провери интернет връзката, DNS/VPN настройките или опитай отново по-късно.")


def find_best_release(provider, artist: str, album: str):
    try:
        results = provider.search(artist, album)
    except PROVIDER_REQUEST_ERRORS as exc:
        print_provider_request_error(provider, exc, "търсене на metadata")
        return None

    if not results:
        print("Няма намерени релийзи.")
        return None

    best = provider.pick_best(results, artist, album)
    if not best:
        print("Няма подходящ релийз.")
        return None

    return best


def build_release_data(provider, release):
    try:
        return provider.extract_metadata(release), provider.build_trackmap(release)
    except PROVIDER_REQUEST_ERRORS as exc:
        print_provider_request_error(provider, exc, "извличане на детайли за релийза")
        return None


def resolve_album_context(album_dir: str, args):
    artist, album = resolve_artist_album(album_dir, args.artist, args.album)

    if not artist or not album:
        print(f"Неуспешно извличане на artist/album за: {album_dir}")
        print("Подай ги ръчно с --artist и --album.")
        return None

    return artist, album


def resolve_sfa_file_context(audio_file: str, args):
    artist, album = resolve_artist_album_from_audio_file(audio_file, args.artist, args.album)

    if not artist or not album:
        print(f"Неуспешно извличане на artist/album за SFA файл: {audio_file}")
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
