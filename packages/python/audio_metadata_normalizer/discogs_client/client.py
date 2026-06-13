# discogs_client/client.py
import os
import discogs_client


class DiscogsClient:
    """
    Discogs API client wrapper.
    Осигурява единна точка за достъп до Discogs API,
    така че останалите модули (search, trackmap, chapters)
    да работят чрез този клиент, без да знаят детайли за API-то.
    """

    def __init__(self, user_token=None, app_name: str = "AngelAudioTagger/1.0"):
        """
        Инициализация на Discogs клиента.

        :param user_token: Personal Access Token от Discogs
        :param app_name: Име на приложението, което се изпраща към Discogs API
        """
        token = user_token or os.getenv("DISCOGS_TOKEN")
        if not token:
            raise ValueError("DiscogsClient requires a valid user_token or DISCOGS_TOKEN env variable")

        self.client = discogs_client.Client(
            app_name,
            user_token=token
        )

    def search(self, **kwargs):
        """
        Унифициран метод за търсене.
        Препраща параметрите директно към Discogs API search().

        Пример:
            client.search(artist="Ron Kenoly", release_title="Sing Out")
        """
        return self.client.search(**kwargs)

    def get_release(self, release_id: int):
        """
        Връща пълен Discogs Release обект по ID.
        """
        return self.client.release(release_id)

    def get_master(self, master_id: int):
        """
        Връща Master Release обект.
        """
        return self.client.master(master_id)
