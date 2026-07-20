"""add 'tv' to the item type CHECK constraint

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-21
"""
from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_items_type", "items", type_="check")
    op.create_check_constraint(
        "ck_items_type", "items", "type IN ('book', 'movie', 'tv', 'game')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_items_type", "items", type_="check")
    op.create_check_constraint(
        "ck_items_type", "items", "type IN ('book', 'movie', 'game')"
    )
