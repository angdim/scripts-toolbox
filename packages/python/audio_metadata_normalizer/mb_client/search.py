# mb_client/search.py

"""
Модул за търсене на релийзи в MusicBrainz.
Работи чрез MBClient и предоставя унифициран интерфейс,
идентичен на този в discogs_client/search.py.
"""

from typing import List, Any


def search_album(client, artist: str, album: str) -> List[Any]:
    """
    Търси релийзи в MusicBrainz по artist + album.
    Връща списък от release dict обекти.

    :param client: MBClient инстанция
    :param artist: име на изпълнител
    :param album: име на албум
    :return: списък от release dict обекти
    """

    if not artist or not album:
        raise ValueError("search_album() requires both artist and album")

    # MusicBrainz search API
    results = client.search_releases(artist, album)

    # Връща списък от release dict обекти
    return results


def search_by_release_group(client, artist: str, album: str) -> List[Any]:
    """
    Търси release-groups (по-общи издания).
    Полезно, ако искаме да намерим каноничната версия на албума.

    :param client: MBClient инстанция
    :param artist: изпълнител
    :param album: албум
    :return: списък от release-group dict обекти
    """

    result = client.search_releases(artist, album)

    # MusicBrainz връща release-list, но release-group е вътре в release
    groups = []
    for r in result:
        if "release-group" in r:
            groups.append(r["release-group"])

    return groups
