"""TMDB — movies. Requires TMDB_API_KEY (v3 key).

Docs: https://developer.themoviedb.org/reference/search-movie
"""

import httpx

from app.config import get_settings
from app.domain.enums import ItemType
from app.providers.base import MetadataProvider, MetadataResult
from app.providers.cache import cached_fetch

BASE = "https://api.themoviedb.org/3"
POSTER_URL = "https://image.tmdb.org/t/p/w500{path}"


class TmdbProvider(MetadataProvider):
    name = "tmdb"
    item_type = ItemType.MOVIE

    @property
    def available(self) -> bool:
        return bool(get_settings().tmdb_api_key)

    def search(self, query: str) -> list[MetadataResult]:
        if not self.available:
            return []

        endpoint = "tv" if self.item_type == ItemType.TV else "movie"

        def fetch() -> dict:
            res = httpx.get(
                f"{BASE}/search/{endpoint}",
                params={"api_key": get_settings().tmdb_api_key, "query": query},
                timeout=10,
            )
            res.raise_for_status()
            return res.json()

        try:
            data = cached_fetch(self.db, self.name, f"search:{endpoint}:{query.lower()}", fetch)
        except httpx.HTTPError:
            return []
        # TMDB's own ranking mixes relevance and recency; surface the most
        # popular titles first so the obvious pick sits at the top.
        ranked = sorted(
            data.get("results", []),
            key=lambda m: m.get("popularity") or 0,
            reverse=True,
        )
        return [self._map_result(m) for m in ranked[:10]]

    def details(self, external_id: str) -> MetadataResult | None:
        """Full record (director/creator, runtime) once the user picks a result."""
        if not self.available:
            return None

        endpoint = "tv" if self.item_type == ItemType.TV else "movie"

        def fetch() -> dict:
            res = httpx.get(
                f"{BASE}/{endpoint}/{external_id}",
                params={"api_key": get_settings().tmdb_api_key, "append_to_response": "credits"},
                timeout=10,
            )
            res.raise_for_status()
            return res.json()

        try:
            data = cached_fetch(self.db, self.name, f"details:{endpoint}:{external_id}", fetch)
        except httpx.HTTPError:
            return None
        result = self._map_result(data)
        if self.item_type == ItemType.MOVIE:
            result.metadata["runtime"] = data.get("runtime")
        else:
            # Ongoing shows report episode_run_time as [] — treat like missing.
            result.metadata["episode_runtime"] = (data.get("episode_run_time") or [None])[0]
            result.metadata["number_of_episodes"] = data.get("number_of_episodes")
            result.metadata["number_of_seasons"] = data.get("number_of_seasons")
            # Consumed at item creation (core/seasons.py) into item_seasons rows.
            result.metadata["seasons"] = [
                {
                    "tmdb_season_id": s.get("id"),
                    "season_number": s["season_number"],
                    "name": s.get("name"),
                    "episode_count": s.get("episode_count"),
                    "air_date": s.get("air_date") or None,
                    "poster_path": s.get("poster_path"),
                }
                for s in data.get("seasons", [])
                if s.get("season_number") is not None
            ]

        # TMDB community score; 0 means unrated, not "rated zero".
        rating = data.get("vote_average")
        result.metadata["tmdb_rating"] = round(rating, 1) if rating else None

        director = next(
            (c["name"] for c in data.get("credits", {}).get("crew", []) if c.get("job") == "Director"),
            None,
        )
        if not director and self.item_type == ItemType.TV:
            director = next(
                (c["name"] for c in data.get("created_by", [])),
                None,
            )
        result.metadata["director"] = director
        return result

    def season_episodes(
        self, external_id: str, season_number: int, force: bool = False
    ) -> list[dict]:
        """Episode list for one season — the extra call per season TMDB needs.

        Fetched lazily (core/episodes.py) the first time a season is opened;
        `force` re-asks TMDB for a running show that has gained episodes.
        """
        if not self.available:
            return []

        def fetch() -> dict:
            res = httpx.get(
                f"{BASE}/tv/{external_id}/season/{season_number}",
                params={"api_key": get_settings().tmdb_api_key},
                timeout=10,
            )
            res.raise_for_status()
            return res.json()

        try:
            data = cached_fetch(
                self.db, self.name, f"season:{external_id}:{season_number}", fetch, force=force
            )
        except httpx.HTTPError:
            return []
        return [
            {
                "tmdb_episode_id": e.get("id"),
                "episode_number": e["episode_number"],
                "name": e.get("name") or None,
                "overview": e.get("overview") or None,
                "air_date": e.get("air_date") or None,
                "runtime": e.get("runtime"),
            }
            for e in data.get("episodes", [])
            if isinstance(e.get("episode_number"), int)
        ]

    def _map_result(self, data: dict) -> MetadataResult:
        is_tv = self.item_type == ItemType.TV
        title = data.get("name" if is_tv else "title", "Unknown")
        release = data.get("first_air_date" if is_tv else "release_date") or ""
        poster = data.get("poster_path")
        return MetadataResult(
            title=title,
            item_type=self.item_type,
            metadata={
                "tmdb_id": data.get("id"),
                "year": int(release[:4]) if len(release) >= 4 else None,
                "release_date": release if len(release) == 10 else None,
                "overview": data.get("overview"),
            },
            cover_url=POSTER_URL.format(path=poster) if poster else None,
            external_id=str(data.get("id")),
        )
