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

        def fetch() -> dict:
            res = httpx.get(
                f"{BASE}/search/movie",
                params={"api_key": get_settings().tmdb_api_key, "query": query},
                timeout=10,
            )
            res.raise_for_status()
            return res.json()

        try:
            data = cached_fetch(self.db, self.name, f"search:{query.lower()}", fetch)
        except httpx.HTTPError:
            return []
        return [self._map_movie(m) for m in data.get("results", [])[:10]]

    def details(self, external_id: str) -> MetadataResult | None:
        """Full record (director, runtime) once the user picks a result."""
        if not self.available:
            return None

        def fetch() -> dict:
            res = httpx.get(
                f"{BASE}/movie/{external_id}",
                params={"api_key": get_settings().tmdb_api_key, "append_to_response": "credits"},
                timeout=10,
            )
            res.raise_for_status()
            return res.json()

        try:
            movie = cached_fetch(self.db, self.name, f"details:{external_id}", fetch)
        except httpx.HTTPError:
            return None
        result = self._map_movie(movie)
        result.metadata["runtime"] = movie.get("runtime")
        director = next(
            (c["name"] for c in movie.get("credits", {}).get("crew", []) if c.get("job") == "Director"),
            None,
        )
        result.metadata["director"] = director
        return result

    def _map_movie(self, movie: dict) -> MetadataResult:
        release = movie.get("release_date") or ""
        poster = movie.get("poster_path")
        return MetadataResult(
            title=movie.get("title", "Unknown"),
            item_type=ItemType.MOVIE,
            metadata={
                "tmdb_id": movie.get("id"),
                "year": int(release[:4]) if len(release) >= 4 else None,
                "release_date": release if len(release) == 10 else None,
                "overview": movie.get("overview"),
            },
            cover_url=POSTER_URL.format(path=poster) if poster else None,
            external_id=str(movie.get("id")),
        )
