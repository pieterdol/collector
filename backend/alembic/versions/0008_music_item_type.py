"""add 'music' to the item type CHECK constraint

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-27
"""
from collections.abc import Sequence

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_items_type", "items", type_="check")
    op.create_check_constraint(
        "ck_items_type", "items", "type IN ('book', 'movie', 'tv', 'game', 'music')"
    )


def downgrade() -> None:
    # Albums would violate the narrower CHECK, so they go first.
    op.execute("DELETE FROM items WHERE type = 'music'")
    op.drop_constraint("ck_items_type", "items", type_="check")
    op.create_check_constraint(
        "ck_items_type", "items", "type IN ('book', 'movie', 'tv', 'game')"
    )
