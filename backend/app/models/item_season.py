import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.enums import DiscMedia, ItemFormat, SeasonOwnership, values
from app.models.item import _check_in

if TYPE_CHECKING:
    from app.models.item_episode import ItemEpisode


class ItemSeason(Base):
    """Per-season ownership and watch state for a TV item.

    Rows are created from TMDB season metadata at item creation, or lazily
    by the season PATCH endpoint (manual entries). The show-level
    format/metadata.media remain the whole-show fallback (box sets) when
    no season is tracked. Episodes hang off this row (item_episodes),
    filled in lazily the first time the season is opened.
    """

    __tablename__ = "item_seasons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE")
    )

    season_number: Mapped[int] = mapped_column(Integer)  # 0 = Specials
    tmdb_season_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(Text)
    episode_count: Mapped[int | None] = mapped_column(Integer)
    air_date: Mapped[date | None] = mapped_column(Date)
    poster_path: Mapped[str | None] = mapped_column(Text)  # local /media path

    # NULL = auto-created row nobody has touched yet.
    ownership: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(Text)
    media: Mapped[str | None] = mapped_column(Text)
    watched: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Eager-loaded: every season read reports its episode progress, and the
    # counts are a handful of rows per season.
    episodes: Mapped[list["ItemEpisode"]] = relationship(
        cascade="all, delete-orphan",
        order_by="ItemEpisode.episode_number",
        lazy="selectin",
    )

    @property
    def episodes_tracked(self) -> int:
        return len(self.episodes)

    @property
    def episodes_watched(self) -> int:
        return sum(1 for e in self.episodes if e.watched)

    __table_args__ = (
        UniqueConstraint("item_id", "season_number", name="uq_item_seasons_item_season"),
        CheckConstraint(
            _check_in("ownership", values(SeasonOwnership)), name="ck_item_seasons_ownership"
        ),
        CheckConstraint(_check_in("format", values(ItemFormat)), name="ck_item_seasons_format"),
        CheckConstraint(_check_in("media", values(DiscMedia)), name="ck_item_seasons_media"),
        CheckConstraint("season_number >= 0", name="ck_item_seasons_season_number"),
        Index("ix_item_seasons_item_id", "item_id"),
    )
