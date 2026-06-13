# discogs_client/search.py

"""
Модул за търсене на релийзи в Discogs.
Работи чрез DiscogsClient и предоставя унифициран интерфейс,
идентичен на този в mb_client/search.py.
"""

from typing import List, Any


def search_album(client, artist: str, album: str) -> List[Any]:
    """
    Търси релийзи в Discogs по artist + album.
    Връща списък от Discogs Release обекти (не нормализирани).

    :param client: DiscogsClient.client (вътрешният API клиент)
    :param artist: име на изпълнител
    :param album: име на албум
    :return: списък от Discogs release резултати
    """

    if not artist or not album:
        raise ValueError("search_album() requires both artist and album")

    # Discogs search API
    results = client.search(
        artist=artist,
        release_title=album,
        type="release"
    )

    # Discogs връща SearchResultSequence, което се държи като списък
    return list(results)


def search_by_catalog_number(client, catno: str) -> List[Any]:
    """
    Търси релийзи по каталожен номер (Discogs е много силен в това).
    Полезно за CD/Vinyl издания.

    :param client: DiscogsClient.client
    :param catno: каталожен номер (пример: "IMD14741")
    :return: списък от релийзи
    """
    if not catno:
        raise ValueError("search_by_catalog_number() requires catno")

    results = client.search(
        catno=catno,
        type="release"
    )

    return list(results)


def search_master(client, artist: str, album: str) -> List[Any]:
    """
    Търси master releases (по-общи издания).
    Полезно, ако искаме да вземем най-каноничната версия.

    :param client: DiscogsClient.client
    :param artist: изпълнител
    :param album: албум
    :return: списък от master releases
    """
    results = client.search(
        artist=artist,
        release_title=album,
        type="master"
    )

    return list(results)
