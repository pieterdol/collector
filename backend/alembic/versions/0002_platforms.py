"""platforms table + items.platform_id, backfilled from metadata

Revision ID: a1b2c3d4e5f6
Revises: 96db89ddb95c
Create Date: 2026-07-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "96db89ddb95c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platforms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("igdb_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("abbreviation", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("igdb_id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column("items", sa.Column("platform_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_items_platform_id", "items", "platforms", ["platform_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_items_platform_id", "items", ["platform_id"])

    # Backfill: every distinct platform string on existing games becomes a
    # (custom) platform row, and those games are linked to it.
    op.execute(
        """
        INSERT INTO platforms (id, name)
        SELECT gen_random_uuid(), metadata->>'platform'
        FROM items
        WHERE type = 'game' AND metadata->>'platform' IS NOT NULL
        GROUP BY metadata->>'platform'
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE items SET platform_id = p.id
        FROM platforms p
        WHERE items.type = 'game' AND items.metadata->>'platform' = p.name
        """
    )


def downgrade() -> None:
    op.drop_index("ix_items_platform_id", table_name="items")
    op.drop_constraint("fk_items_platform_id", "items", type_="foreignkey")
    op.drop_column("items", "platform_id")
    op.drop_table("platforms")
