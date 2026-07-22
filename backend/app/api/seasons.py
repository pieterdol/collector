"""Per-season ownership and watch state for TV items.

Season rows are auto-created from TMDB metadata at item creation
(core/seasons.py); PATCH upserts, so manual entries grow rows on first
touch. Every mutation records an activity event in the same transaction.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.items import _get_owned_item
from app.core.events import record_event
from app.core.security import get_current_user
from app.db import get_db
from app.domain.enums import EventType, SeasonOwnership
from app.models import Item, ItemSeason, User
from app.schemas.season import SeasonListOut, SeasonOut, SeasonUpdate

router = APIRouter(prefix="/api/items/{item_id}/seasons", tags=["seasons"])

SeasonNumber = Annotated[int, Path(ge=0)]


@router.get("", response_model=SeasonListOut)
def list_seasons(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SeasonListOut:
    item = _get_owned_item(db, user, item_id)
    rows = db.scalars(
        select(ItemSeason)
        .where(ItemSeason.item_id == item.id)
        .order_by(ItemSeason.season_number)
    ).all()
    regular = [r for r in rows if r.season_number >= 1]
    return SeasonListOut(
        seasons=[SeasonOut.model_validate(r) for r in rows],
        total_seasons=len(regular),
        owned_seasons=sum(1 for r in regular if r.ownership == SeasonOwnership.OWNED.value),
        watched_seasons=sum(1 for r in regular if r.watched),
    )


@router.patch("/{season_number}", response_model=SeasonOut)
def update_season(
    item_id: uuid.UUID,
    season_number: SeasonNumber,
    body: SeasonUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemSeason:
    item = _get_owned_item(db, user, item_id)
    if item.type != "tv":
        raise HTTPException(status_code=400, detail="Seasons apply to TV shows only")
    season = _get_or_create_season(db, item, season_number)

    changed: dict = {}
    old: dict = {}
    for name, value in body.model_dump(exclude_unset=True).items():
        value = value.value if hasattr(value, "value") else value
        if getattr(season, name) != value:
            old[name] = getattr(season, name)
            changed[name] = value
            setattr(season, name, value)

    _record_season_events(db, item, user, season, old, changed)
    db.commit()
    db.refresh(season)
    return season


@router.delete("/{season_number}", status_code=204)
def delete_season(
    item_id: uuid.UUID,
    season_number: SeasonNumber,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Remove one tracked season (e.g. a manually added row)."""
    item = _get_owned_item(db, user, item_id)
    season = db.scalar(
        select(ItemSeason).where(
            ItemSeason.item_id == item.id, ItemSeason.season_number == season_number
        )
    )
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    record_event(
        db,
        item_id=item.id,
        user_id=user.id,
        event_type=EventType.SEASON_REMOVED,
        old_value={
            "season_number": season.season_number,
            "ownership": season.ownership,
            "format": season.format,
            "media": season.media,
            "watched": season.watched,
        },
    )
    db.delete(season)
    db.commit()


def _get_or_create_season(db: Session, item: Item, season_number: int) -> ItemSeason:
    season = db.scalar(
        select(ItemSeason).where(
            ItemSeason.item_id == item.id, ItemSeason.season_number == season_number
        )
    )
    if season is None:
        season = ItemSeason(item_id=item.id, season_number=season_number)
        db.add(season)
        db.flush()  # apply defaults so the change diff sees them
    return season


def _record_season_events(db, item, user, season, old, changed) -> None:
    """One event per meaningful change, in the caller's transaction."""
    n = season.season_number
    acquired = changed.get("ownership") == SeasonOwnership.OWNED.value
    if acquired:
        record_event(
            db,
            item_id=item.id,
            user_id=user.id,
            event_type=EventType.SEASON_ACQUIRED,
            old_value={"season_number": n, "ownership": old.get("ownership")},
            new_value={
                "season_number": n,
                "ownership": season.ownership,
                "format": season.format,
                "media": season.media,
            },
        )
    if "watched" in changed:
        record_event(
            db,
            item_id=item.id,
            user_id=user.id,
            event_type=EventType.SEASON_WATCHED,
            old_value={"season_number": n, "watched": old["watched"]},
            new_value={"season_number": n, "watched": changed["watched"]},
        )
    # Everything not already carried by the events above.
    covered = {"watched"} | ({"ownership", "format", "media"} if acquired else set())
    other = {k: v for k, v in changed.items() if k not in covered}
    if other:
        record_event(
            db,
            item_id=item.id,
            user_id=user.id,
            event_type=EventType.SEASON_UPDATED,
            old_value={"season_number": n, **{k: old[k] for k in other}},
            new_value={"season_number": n, **other},
        )
