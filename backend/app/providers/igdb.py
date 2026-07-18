"""IGDB — games. Requires TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET.

IGDB authenticates with a Twitch app token (client-credentials flow);
the token is kept in memory and refreshed shortly before it expires.
Docs: https://api-docs.igdb.com/#games
"""

import time
from datetime import UTC, datetime

import httpx

from app.config import get_settings
from app.domain.enums import ItemType
from app.providers.base import MetadataProvider, MetadataResult
from app.providers.cache import cached_fetch

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
GAMES_URL = "https://api.igdb.com/v4/games"
EXTERNAL_GAMES_URL = "https://api.igdb.com/v4/external_games"
COVER_URL = "https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
STEAM_SOURCE = 1  # external_games.external_game_source for Steam

_token: dict = {"value": None, "expires": 0.0}


def covers_for_steam_appids(db, steam_appids: list[int]) -> dict[int, str]:
    """Module-level convenience: {} when IGDB isn't configured."""
    provider = IgdbProvider(db)
    if not provider.available or not steam_appids:
        return {}
    return provider.external_covers(steam_appids)


def _iso(timestamp) -> str | None:
    return datetime.fromtimestamp(timestamp, UTC).date().isoformat() if timestamp else None


def release_dates_for_steam_appids(db, steam_appids: list[int]) -> dict[int, str]:
    """Steam appid → ISO release date via IGDB's external mapping, batched."""
    provider = IgdbProvider(db)
    if not provider.available or not steam_appids:
        return {}
    out: dict[int, str] = {}
    for start in range(0, len(steam_appids), 100):
        chunk = steam_appids[start : start + 100]
        uid_list = ",".join(f'"{appid}"' for appid in chunk)
        body = (
            "fields uid, game.first_release_date; "
            f"where external_game_source = {STEAM_SOURCE} & uid = ({uid_list}); limit 500;"
        )
        try:
            res = httpx.post(
                EXTERNAL_GAMES_URL,
                content=body,
                headers={
                    "Client-ID": get_settings().twitch_client_id,
                    "Authorization": f"Bearer {provider._token()}",
                },
                timeout=15,
            )
            res.raise_for_status()
        except httpx.HTTPError:
            continue
        for entry in res.json():
            uid = entry.get("uid", "")
            date = _iso((entry.get("game") or {}).get("first_release_date"))
            if uid.isdigit() and date:
                out[int(uid)] = date
        if start + 100 < len(steam_appids):
            time.sleep(0.3)
    return out


def release_dates_for_igdb_ids(db, igdb_ids: list[int]) -> dict[int, str]:
    """IGDB game id → ISO release date, batched."""
    provider = IgdbProvider(db)
    if not provider.available or not igdb_ids:
        return {}
    out: dict[int, str] = {}
    for start in range(0, len(igdb_ids), 100):
        chunk = igdb_ids[start : start + 100]
        id_list = ",".join(str(i) for i in chunk)
        body = f"fields first_release_date; where id = ({id_list}); limit 500;"
        try:
            res = httpx.post(
                GAMES_URL,
                content=body,
                headers={
                    "Client-ID": get_settings().twitch_client_id,
                    "Authorization": f"Bearer {provider._token()}",
                },
                timeout=15,
            )
            res.raise_for_status()
        except httpx.HTTPError:
            continue
        for entry in res.json():
            date = _iso(entry.get("first_release_date"))
            if entry.get("id") and date:
                out[int(entry["id"])] = date
        if start + 100 < len(igdb_ids):
            time.sleep(0.3)
    return out


class IgdbProvider(MetadataProvider):
    name = "igdb"
    item_type = ItemType.GAME

    @property
    def available(self) -> bool:
        settings = get_settings()
        return bool(settings.twitch_client_id and settings.twitch_client_secret)

    def search(self, query: str) -> list[MetadataResult]:
        if not self.available:
            return []

        def fetch() -> dict:
            safe_query = query.replace('"', "")
            body = (
                f'search "{safe_query}"; '
                "fields name,first_release_date,platforms.name,"
                "involved_companies.company.name,involved_companies.developer,"
                "cover.image_id; limit 10;"
            )
            res = httpx.post(
                GAMES_URL,
                content=body,
                headers={
                    "Client-ID": get_settings().twitch_client_id,
                    "Authorization": f"Bearer {self._token()}",
                },
                timeout=10,
            )
            res.raise_for_status()
            return {"games": res.json()}

        try:
            data = cached_fetch(self.db, self.name, f"search:{query.lower()}", fetch)
        except httpx.HTTPError:
            return []
        return [self._map_game(g) for g in data.get("games", [])]

    def _token(self) -> str:
        if _token["value"] and _token["expires"] > time.time() + 60:
            return _token["value"]
        settings = get_settings()
        res = httpx.post(
            TOKEN_URL,
            params={
                "client_id": settings.twitch_client_id,
                "client_secret": settings.twitch_client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        res.raise_for_status()
        payload = res.json()
        _token["value"] = payload["access_token"]
        _token["expires"] = time.time() + payload.get("expires_in", 3600)
        return _token["value"]

    def external_covers(self, steam_appids: list[int]) -> dict[int, str]:
        """Steam appid → IGDB cover URL, via IGDB's external-id mapping.

        Exact ID matching (no fuzzy title search); appids IGDB doesn't
        know, or games without cover art, are simply absent from the map.
        """
        out: dict[int, str] = {}
        for start in range(0, len(steam_appids), 100):
            chunk = steam_appids[start : start + 100]
            uid_list = ",".join(f'"{appid}"' for appid in chunk)
            body = (
                "fields uid, game.cover.image_id; "
                f"where external_game_source = {STEAM_SOURCE} & uid = ({uid_list}); limit 500;"
            )
            try:
                res = httpx.post(
                    EXTERNAL_GAMES_URL,
                    content=body,
                    headers={
                        "Client-ID": get_settings().twitch_client_id,
                        "Authorization": f"Bearer {self._token()}",
                    },
                    timeout=15,
                )
                res.raise_for_status()
            except httpx.HTTPError:
                continue  # partial results are fine
            for entry in res.json():
                uid = entry.get("uid", "")
                image = ((entry.get("game") or {}).get("cover") or {}).get("image_id")
                if uid.isdigit() and image:
                    out[int(uid)] = COVER_URL.format(image_id=image)
            if start + 100 < len(steam_appids):
                time.sleep(0.3)  # stay under IGDB's 4 req/s limit
        return out

    def _map_game(self, game: dict) -> MetadataResult:
        developer = next(
            (
                c["company"]["name"]
                for c in game.get("involved_companies", [])
                if c.get("developer") and c.get("company")
            ),
            None,
        )
        release = game.get("first_release_date")
        release_dt = datetime.fromtimestamp(release, UTC) if release else None
        year = release_dt.year if release_dt else None
        platforms = ", ".join(p["name"] for p in game.get("platforms", []) if p.get("name"))
        cover = (game.get("cover") or {}).get("image_id")
        return MetadataResult(
            title=game.get("name", "Unknown"),
            item_type=ItemType.GAME,
            metadata={
                "igdb_id": game.get("id"),
                "developer": developer,
                "platform": platforms or None,
                "year": year,
                "release_date": release_dt.date().isoformat() if release_dt else None,
            },
            cover_url=COVER_URL.format(image_id=cover) if cover else None,
            external_id=str(game.get("id")),
        )
