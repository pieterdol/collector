import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class EpisodeUpdate(BaseModel):
    """PATCH body: watch state is all the user owns per episode."""

    watched: bool


class EpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    season_id: uuid.UUID
    episode_number: int
    tmdb_episode_id: int | None
    name: str | None
    overview: str | None
    air_date: date | None
    runtime: int | None
    watched: bool
    created_at: datetime
    updated_at: datetime


class EpisodeListOut(BaseModel):
    episodes: list[EpisodeOut]
    total: int
    watched: int
