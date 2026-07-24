"""PSN library import — NPSSO paste-once flow, PS Plus filtered by default."""

import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.events import record_event
from app.core.library_import import fetch_covers
from app.core.platforms import find_or_create_platform
from app.core.security import get_current_user
from app.db import get_db
from app.domain.enums import EventType, ItemFormat, ItemStatus, ItemType
from app.models import Item, User
from app.providers.psn import PsnError, exchange_npsso, purchased_games
from app.schemas.library_import import LibraryImportOut

router = APIRouter(prefix="/api/psn", tags=["psn"])

# PSN platform tags → IGDB platform names (the platforms table's spelling).
_PLATFORM_NAMES = {
    "PS5": "PlayStation 5",
    "PS4": "PlayStation 4",
    "PS3": "PlayStation 3",
    "PSVITA": "PlayStation Vita",
    "PSP": "PlayStation Portable",
}


class PsnImportIn(BaseModel):
    # The NPSSO cookie value from ca.account.sony.com/api/v1/ssocookie.
    npsso: str = Field(min_length=10, max_length=4000)
    include_ps_plus: bool = False


@router.post("/import", response_model=LibraryImportOut)
def import_psn_library(
    body: PsnImportIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LibraryImportOut:
    """Bulk-create digital game items from a PSN purchased list.

    PS Plus-gated claims are excluded unless include_ps_plus is set;
    when included they carry metadata.subscription = "PS Plus" so they
    stay identifiable if the subscription ever lapses.
    """
    try:
        token = exchange_npsso(body.npsso)
        games = purchased_games(token, body.include_ps_plus)
    except PsnError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="PSN is unreachable right now")

    existing = set(
        db.scalars(
            select(text("metadata->>'psn_title_id'")).select_from(Item).where(
                Item.user_id == user.id,
                Item.type == ItemType.GAME.value,
                text("metadata ? 'psn_title_id'"),
            )
        )
    )

    platforms: dict[str, uuid.UUID] = {}
    imported_ids: list[uuid.UUID] = []
    for game in games:
        title_id = game.get("titleId")
        title = game.get("name")
        if not title_id or not title or title_id in existing:
            continue
        existing.add(title_id)

        platform_name = _PLATFORM_NAMES.get(game.get("platform"), "PlayStation 5")
        if platform_name not in platforms:
            platforms[platform_name] = find_or_create_platform(db, platform_name).id

        meta = {
            "psn_title_id": title_id,
            "storefront": "PlayStation Store",
            "platform": platform_name,
        }
        cover = (game.get("image") or {}).get("url")
        if isinstance(cover, str) and cover.startswith("http"):
            meta["cover_source_url"] = cover
        if game.get("subscription"):
            meta["subscription"] = game["subscription"]

        item = Item(
            user_id=user.id,
            type=ItemType.GAME.value,
            format=ItemFormat.DIGITAL.value,
            status=ItemStatus.BACKLOG.value,
            platform_id=platforms[platform_name],
            title=title,
            meta=meta,
        )
        db.add(item)
        db.flush()
        record_event(
            db,
            item_id=item.id,
            user_id=user.id,
            event_type=EventType.ITEM_ADDED,
            new_value={"status": item.status, "type": item.type, "title": item.title,
                       "source": "psn_import"},
        )
        imported_ids.append(item.id)
    db.commit()

    if imported_ids:
        background.add_task(fetch_covers, imported_ids)

    return LibraryImportOut(
        imported=len(imported_ids),
        skipped=len(games) - len(imported_ids),
        total=len(games),
    )
