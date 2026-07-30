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

    # Reading a title off a photographed cover, via a local Ollama. Empty
    # URL disables the feature and the UI hides the photo tab.
    ollama_url: str = ""
    #: Reader: real OCR of the printed title. Degrades by dropping words it
    #: cannot make out, which is the safe direction.
    vision_model: str = "qwen3-vl:4b"
    #: Recogniser: names a cover it knows from the art alone — catches
    #: stylised logos OCR can't read, at the price of confident invention.
    #: Both answers are only ever search terms; the catalog decides. Empty
    #: to run the reader alone.
    vision_recognizer_model: str = "moondream"
    vision_timeout_seconds: int = 90

    # Provider lookup cache TTL
    provider_cache_ttl_hours: int = 24 * 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
