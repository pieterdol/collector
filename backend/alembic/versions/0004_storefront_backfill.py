"""stamp storefront='Steam' on existing Steam imports

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-07-18
"""
from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE items
        SET metadata = jsonb_set(metadata, '{storefront}', '"Steam"')
        WHERE type = 'game'
          AND metadata ? 'steam_appid'
          AND NOT metadata ? 'storefront'
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE items SET metadata = metadata - 'storefront' "
        "WHERE type = 'game' AND metadata ? 'steam_appid'"
    )
