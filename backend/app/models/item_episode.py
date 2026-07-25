import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ItemEpisode(Base):
    """One episode of a tracked TV season, with its own watch flag.

    Rows are filled lazily from TMDB the first time a season is opened
    (core/episodes.py) — a show nobody expands never costs an API call.
    They hang off item_seasons, so removing a season (or the show) takes
    its episodes with it. Watch state syncs both ways with the season
    flag: the last episode ticked marks the season watched.
    """

    __tablename__ = "item_episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_seasons.id", ondelete="CASCADE")
    )

    episode_number: Mapped[int] = mapped_column(Integer)
    tmdb_episode_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(Text)
    overview: Mapped[str | None] = mapped_column(Text)
    air_date: Mapped[date | None] = mapped_column(Date)
    runtime: Mapped[int | None] = mapped_column(Integer)  # minutes
    watched: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("season_id", "episode_number", name="uq_item_episodes_season_episode"),
        CheckConstraint("episode_number >= 0", name="ck_item_episodes_episode_number"),
        Index("ix_item_episodes_season_id", "season_id"),
    )
