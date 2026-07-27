"""Application settings, loaded from environment variables.

Every external key is optional: a missing key disables the matching
metadata provider and the UI falls back to manual entry.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://collector:collector@localhost:5432/collector"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 30  # 30 days; household app, long sessions
    media_dir: str = "/data/media"

    # Provider keys (all optional)
    tmdb_api_key: str = ""
    twitch_client_id: str = ""
    twitch_client_secret: str = ""
    steam_api_key: str = ""
    # Optional upgrade for music: without it, MusicBrainz (keyless) is used.
    discogs_token: str = ""

    # Provider lookup cache TTL
    provider_cache_ttl_hours: int = 24 * 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
