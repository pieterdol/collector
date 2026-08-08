import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.enums import ItemFormat, ItemStatus, ItemType, values
from app.domain.platforms import names_one_platform


def _check_in(column: str, allowed: list[str]) -> str:
    quoted = ", ".join(f"'{v}'" for v in allowed)
    return f"{column} IN ({quoted})"


class Item(Base):
    """One entry in a user's collection.

    Type-specific fields (authors, director, platform, …) live in the JSONB
    `metadata` column — see app/schemas/item.py for the per-type shapes.
    """

    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # Games link to a platform record; other types leave this NULL.
    platform_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platforms.id", ondelete="SET NULL")
    )

    # Copies of the same release (a game on PS5 and PC, a DVD later replaced
    # by a Blu-ray) share a bundle id: separate items, one library entry.
    # Deliberately not a FK to a bundles table — membership lives on the
    # copies, so deleting one can never leave a dangling group behind.
    bundle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # The one copy of a bundle the library grid shows.
    bundle_front: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    type: Mapped[str] = mapped_column(Text)
    # Format may be unknown while an item is still on the wishlist.
    format: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default=ItemStatus.BACKLOG.value)

    title: Mapped[str] = mapped_column(Text)
    cover_path: Mapped[str | None] = mapped_column(Text)
    # Attribute is `meta` because `metadata` is reserved on declarative models.
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'"))

    progress_current: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    progress_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    review: Mapped[str | None] = mapped_column(Text)

    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str | None] = mapped_column(Text)
    acquisition_date: Mapped[date | None] = mapped_column(Date)

    borrowed_by: Mapped[str | None] = mapped_column(Text)
    loaned_date: Mapped[date | None] = mapped_column(Date)
    returned_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Set when status enters `completed`; kept for completions-per-period stats.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    title_tsv = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', title)", persisted=True)
    )

    platform_ref = relationship("Platform", lazy="selectin")

    @property
    def platform(self) -> str | None:
        """Platform name for API output; legacy items fall back to metadata."""
        if self.platform_ref is not None:
            return self.platform_ref.name
        value = self.meta.get("platform")
        # Unlinked means nothing was picked — never show the release list a
        # catalog left behind (see app/domain/platforms.py).
        return value if names_one_platform(value) else None

    __table_args__ = (
        CheckConstraint(_check_in("type", values(ItemType)), name="ck_items_type"),
        CheckConstraint(_check_in("format", values(ItemFormat)), name="ck_items_format"),
        CheckConstraint(_check_in("status", values(ItemStatus)), name="ck_items_status"),
        CheckConstraint(
            "rating >= 0 AND rating <= 5 AND rating * 2 = floor(rating * 2)",
            name="ck_items_rating_half_steps",
        ),
        CheckConstraint(
            "NOT bundle_front OR bundle_id IS NOT NULL",
            name="ck_items_bundle_front_needs_bundle",
        ),
        Index("ix_items_user_bundle", "user_id", "bundle_id"),
        # At most one copy fronts a bundle.
        Index(
            "uq_items_bundle_front",
            "bundle_id",
            unique=True,
            postgresql_where=text("bundle_front"),
        ),
        Index("ix_items_user_type_status", "user_id", "type", "status"),
        Index("ix_items_user_format", "user_id", "format"),
        Index("ix_items_platform_id", "platform_id"),
        Index(
            "ix_items_user_completed_at",
            "user_id",
            "completed_at",
            postgresql_where=text("completed_at IS NOT NULL"),
        ),
        Index("ix_items_title_tsv", "title_tsv", postgresql_using="gin"),
    )
