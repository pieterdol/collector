"""Platform records: IGDB sync (once) and find-or-create linking."""

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Platform
from app.providers.igdb import IgdbProvider

IGDB_PLATFORMS_URL = "https://api.igdb.com/v4/platforms"

# Below this many rows the table is considered unsynced (custom rows only).
SYNCED_THRESHOLD = 20


def find_or_create_platform(db: Session, name: str) -> Platform:
    """Resolve a platform name to its row, creating a custom row if new."""
    clean = name.strip()
    platform = db.scalar(select(Platform).where(func.lower(Platform.name) == clean.lower()))
    if platform is None:
        platform = Platform(name=clean)
        db.add(platform)
        db.flush()
    return platform


def ensure_platforms_synced(db: Session) -> bool:
    """Pull the full platform list from IGDB, once. Safe to call repeatedly."""
    count = db.scalar(select(func.count()).select_from(Platform)) or 0
    if count >= SYNCED_THRESHOLD:
        return False
    provider = IgdbProvider(db)
    if not provider.available:
        return False

    try:
        res = httpx.post(
            IGDB_PLATFORMS_URL,
            content="fields name,abbreviation; limit 500; sort name asc;",
            headers={
                "Client-ID": get_settings().twitch_client_id,
                "Authorization": f"Bearer {provider._token()}",
            },
            timeout=20,
        )
        res.raise_for_status()
    except httpx.HTTPError:
        return False

    existing_by_igdb = {
        p.igdb_id: p for p in db.scalars(select(Platform).where(Platform.igdb_id.is_not(None)))
    }
    existing_names = {p.name.lower() for p in db.scalars(select(Platform))}
    for entry in res.json():
        name = entry.get("name")
        if not name or entry["id"] in existing_by_igdb:
            continue
        if name.lower() in existing_names:
            # Custom row created earlier (backfill) — attach the IGDB id.
            row = db.scalar(select(Platform).where(func.lower(Platform.name) == name.lower()))
            if row is not None:
                row.igdb_id = entry["id"]
                row.abbreviation = entry.get("abbreviation")
            continue
        db.add(
            Platform(
                igdb_id=entry["id"], name=name, abbreviation=entry.get("abbreviation")
            )
        )
    db.commit()
    return True
