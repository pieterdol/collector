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
COVER_URL = "https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"

_token: dict = {"value": None, "expires": 0.0}


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
        year = datetime.fromtimestamp(release, UTC).year if release else None
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
            },
            cover_url=COVER_URL.format(image_id=cover) if cover else None,
            external_id=str(game.get("id")),
        )
