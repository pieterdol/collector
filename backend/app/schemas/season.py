import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import DiscMedia, ItemFormat, SeasonOwnership


class SeasonUpdate(BaseModel):
    """PATCH body: only provided fields are applied; explicit nulls clear."""

    ownership: SeasonOwnership | None = None
    format: ItemFormat | None = None
    media: DiscMedia | None = None
    watched: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    episode_count: int | None = Field(default=None, ge=0)


class SeasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    season_number: int
    tmdb_season_id: int | None
    name: str | None
    episode_count: int | None
    air_date: date | None
    poster_path: str | None
    ownership: str | None
    format: str | None
    media: str | None
    watched: bool
    created_at: datetime
    updated_at: datetime


class SeasonListOut(BaseModel):
    seasons: list[SeasonOut]
    # Aggregates skip season 0 (Specials) so they read as show progress.
    total_seasons: int
    owned_seasons: int
    watched_seasons: int
