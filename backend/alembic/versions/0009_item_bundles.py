"""bundle copies of one release under a single library entry

Adds items.bundle_id (opaque group id shared by the copies) and
items.bundle_front (the copy the library grid shows). Nothing to backfill:
existing items are unbundled, which is exactly NULL/false.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("bundle_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "items",
        sa.Column("bundle_front", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_items_bundle_front_needs_bundle", "items", "NOT bundle_front OR bundle_id IS NOT NULL"
    )
    op.create_index("ix_items_user_bundle", "items", ["user_id", "bundle_id"])
    # At most one copy fronts a bundle.
    op.create_index(
        "uq_items_bundle_front",
        "items",
        ["bundle_id"],
        unique=True,
        postgresql_where=sa.text("bundle_front"),
    )


def downgrade() -> None:
    op.drop_index("uq_items_bundle_front", table_name="items")
    op.drop_index("ix_items_user_bundle", table_name="items")
    op.drop_constraint("ck_items_bundle_front_needs_bundle", "items", type_="check")
    op.drop_column("items", "bundle_front")
    op.drop_column("items", "bundle_id")
