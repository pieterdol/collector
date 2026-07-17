"""merge custom 'PC (Steam)' into IGDB's 'PC (Microsoft Windows)' (id 6)

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-18
"""
from collections.abc import Sequence

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ensure the canonical IGDB row exists (works whether or not the
    # catalog sync has already run).
    op.execute(
        """
        INSERT INTO platforms (id, igdb_id, name, abbreviation)
        SELECT gen_random_uuid(), 6, 'PC (Microsoft Windows)', 'PC'
        WHERE NOT EXISTS (
            SELECT 1 FROM platforms WHERE igdb_id = 6 OR name = 'PC (Microsoft Windows)'
        )
        """
    )
    op.execute(
        "UPDATE platforms SET igdb_id = 6 "
        "WHERE name = 'PC (Microsoft Windows)' AND igdb_id IS NULL"
    )
    # Re-link items and rewrite their metadata string, then drop the
    # custom row. Steam ownership stays visible via metadata.steam_appid.
    op.execute(
        """
        UPDATE items
        SET platform_id = (SELECT id FROM platforms WHERE name = 'PC (Microsoft Windows)'),
            metadata = jsonb_set(metadata, '{platform}', '"PC (Microsoft Windows)"')
        WHERE platform_id IN (SELECT id FROM platforms WHERE name = 'PC (Steam)')
        """
    )
    op.execute("DELETE FROM platforms WHERE name = 'PC (Steam)'")


def downgrade() -> None:
    pass  # data merge; not reversible
