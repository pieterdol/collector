"""add item_seasons for per-season TV ownership

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_seasons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("tmdb_season_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("episode_count", sa.Integer(), nullable=True),
        sa.Column("air_date", sa.Date(), nullable=True),
        sa.Column("poster_path", sa.Text(), nullable=True),
        sa.Column("ownership", sa.Text(), nullable=True),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column("media", sa.Text(), nullable=True),
        sa.Column("watched", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("item_id", "season_number", name="uq_item_seasons_item_season"),
        sa.CheckConstraint(
            "ownership IN ('owned', 'wishlist')", name="ck_item_seasons_ownership"
        ),
        sa.CheckConstraint(
            "format IN ('physical', 'digital')", name="ck_item_seasons_format"
        ),
        sa.CheckConstraint(
            "media IN ('DVD', 'Blu-ray', 'Ultra HD Blu-ray', 'VHS')",
            name="ck_item_seasons_media",
        ),
        sa.CheckConstraint("season_number >= 0", name="ck_item_seasons_season_number"),
    )
    op.create_index("ix_item_seasons_item_id", "item_seasons", ["item_id"])


def downgrade() -> None:
    op.drop_table("item_seasons")
