# mb_client/client.py

"""
MBClient — обвивка около musicbrainzngs, която предоставя
унифициран интерфейс за търсене и извличане на релийзи.

Този клас е огледален на DiscogsClient, но адаптиран за MusicBrainz API.
"""

import musicbrainzngs


class MBClient:
    """
    MusicBrainz API клиент.
    Конфигурира musicbrainzngs и предоставя методи за:
    - търсене на релийзи
    - извличане на release по MBID
    """

    def __init__(self, user_agent: str | None = None, contact: str | None = None):
        """
        :param user_agent: име на приложението (пример: "AngelAudioTagger/1.0")
        :param contact: email за MusicBrainz User-Agent policy
        """

        ua = user_agent or "AngelAudioTagger/1.0"
        ct = contact or "example@example.com"

        musicbrainzngs.set_useragent(ua, "1.0", ct)

    # ------------------------------------------------------------
    # 1) Търсене на релийзи
    # ------------------------------------------------------------
    def search_releases(self, artist: str, album: str):
        """
        Търси релийзи по artist + release title.
        Връща списък от release dict обекти.
        """

        result = musicbrainzngs.search_releases(
            artist=artist,
            release=album,
            strict=False,
            limit=50
        )

        return result.get("release-list", [])

    # ------------------------------------------------------------
    # 2) Извличане на release по MBID
    # ------------------------------------------------------------
    def get_release(self, mbid: str):
        """
        Връща пълен release обект с:
        - media
        - tracks
        - labels
        - genres
        - cover-art-archive
        """

        return musicbrainzngs.get_release_by_id(
            mbid,
            includes=[
                "artists",
                "recordings",
                "media",
                "labels",
                "release-groups",
                "genres",
                "tags",
                "cover-art-archive"
            ]
        )["release"]
