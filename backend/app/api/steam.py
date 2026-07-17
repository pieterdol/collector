import uuid
from decimal import Decimal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.covers import download_cover
from app.core.events import record_event
from app.core.security import get_current_user
from app.db import SessionLocal, get_db
from app.domain.enums import EventType, ItemFormat, ItemStatus, ItemType
from app.models import Item, User
from app.providers.steam import LIBRARY_COVER, SteamError, owned_games, resolve_steam_id
from app.schemas.steam import SteamImportIn, SteamImportOut

router = APIRouter(prefix="/api/steam", tags=["steam"])


@router.post("/import", response_model=SteamImportOut)
def import_library(
    body: SteamImportIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SteamImportOut:
    """Bulk-create digital game items from a Steam library.

    Covers are fetched in a background task so importing a large library
    responds quickly; posters fill in shortly after.
    """
    try:
        steam_id = resolve_steam_id(body.steam_id)
        games = owned_games(steam_id)
    except SteamError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Steam API is unreachable right now")

    existing_appids = {
        int(appid)
        for appid in db.scalars(
            select(text("(metadata->>'steam_appid')::int")).select_from(Item).where(
                Item.user_id == user.id,
                Item.type == ItemType.GAME.value,
                text("metadata ? 'steam_appid'"),
            )
        )
    }

    imported_ids: list[uuid.UUID] = []
    skipped = 0
    for game in games:
        if game["appid"] in existing_appids:
            skipped += 1
            continue
        playtime_min = game.get("playtime_forever", 0)
        item = Item(
            user_id=user.id,
            type=ItemType.GAME.value,
            format=ItemFormat.DIGITAL.value,
            status=ItemStatus.BACKLOG.value,
            title=game.get("name", f"App {game['appid']}"),
            meta={
                "steam_appid": game["appid"],
                "platform": "PC (Steam)",
                "playtime_minutes": playtime_min,
                "cover_source_url": LIBRARY_COVER.format(appid=game["appid"]),
            },
            # Playtime prefills progress in hours (games track hours played).
            progress_current=round(Decimal(playtime_min) / 60, 1) if playtime_min else None,
        )
        db.add(item)
        db.flush()
        record_event(
            db,
            item_id=item.id,
            user_id=user.id,
            event_type=EventType.ITEM_ADDED,
            new_value={"status": item.status, "type": item.type, "title": item.title,
                       "source": "steam_import"},
        )
        imported_ids.append(item.id)
    db.commit()

    if imported_ids:
        background.add_task(_fetch_covers, imported_ids)

    return SteamImportOut(imported=len(imported_ids), skipped=skipped, total=len(games))


def _fetch_covers(item_ids: list[uuid.UUID]) -> None:
    """Download library posters for freshly imported games (own session)."""
    with SessionLocal() as db:
        for item_id in item_ids:
            item = db.get(Item, item_id)
            if item is None or item.cover_path:
                continue
            url = item.meta.get("cover_source_url")
            if url:
                item.cover_path = download_cover(url, item.id)
                db.commit()
