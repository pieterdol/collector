"""add item_episodes for per-episode TV watch state

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_episodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "season_id",
            UUID(as_uuid=True),
            sa.ForeignKey("item_seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("tmdb_episode_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("air_date", sa.Date(), nullable=True),
        sa.Column("runtime", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint(
            "season_id", "episode_number", name="uq_item_episodes_season_episode"
        ),
        sa.CheckConstraint("episode_number >= 0", name="ck_item_episodes_episode_number"),
    )
    op.create_index("ix_item_episodes_season_id", "item_episodes", ["season_id"])
    # No backfill: episode lists come from TMDB the first time a season is
    # opened, and seasons already carry their watched flag.


def downgrade() -> None:
    op.drop_table("item_episodes")
