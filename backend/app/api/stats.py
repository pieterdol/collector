"""Aggregates for the Stats page — pure queries over items + activity_events.

No denormalised counters anywhere: the append-only event log and the
timestamp columns make every number here derivable on the fly.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.domain.enums import ItemStatus, ItemType
from app.models import ActivityEvent, Item, User

router = APIRouter(prefix="/api/stats", tags=["stats"])

IN_PROGRESS = ItemStatus.IN_PROGRESS.value
COMPLETED = ItemStatus.COMPLETED.value


@router.get("")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return {
        "tiles": {
            "book": _book_tile(db, user),
            "movie": _movie_tile(db, user),
            "tv": _tv_tile(db, user),
            "game": _game_tile(db, user),
            "music": _music_tile(db, user),
            "value": _value_tile(db, user),
        },
        "continue": _continue_list(db, user),
        "loans": _active_loans(db, user),
        "recent": _recent_activity(db, user),
    }


def _one(db, query):
    return db.execute(query).one()


def _book_tile(db, user) -> dict:
    year_start = datetime(datetime.now(UTC).year, 1, 1, tzinfo=UTC)
    row = _one(
        db,
        select(
            func.count(),
            func.count().filter(Item.status == IN_PROGRESS),
            func.count().filter(Item.completed_at >= year_start),
        ).where(Item.user_id == user.id, Item.type == ItemType.BOOK.value),
    )
    return {"total": row[0], "in_progress": row[1], "completed_this_year": row[2]}


def _movie_tile(db, user) -> dict:
    row = _one(
        db,
        select(
            func.count(),
            func.count().filter(Item.format == "physical"),
            func.count().filter(Item.format == "digital"),
        ).where(Item.user_id == user.id, Item.type == ItemType.MOVIE.value),
    )
    return {"total": row[0], "physical": row[1], "digital": row[2]}


def _tv_tile(db, user) -> dict:
    row = _one(
        db,
        select(
            func.count(),
            func.count().filter(Item.format == "physical"),
            func.count().filter(Item.format == "digital"),
        ).where(Item.user_id == user.id, Item.type == ItemType.TV.value),
    )
    return {"total": row[0], "physical": row[1], "digital": row[2]}


def _game_tile(db, user) -> dict:
    row = _one(
        db,
        select(
            func.count(),
            func.count().filter(text("metadata ? 'steam_appid'")),
            func.coalesce(
                func.sum(
                    case(
                        (Item.status.in_([IN_PROGRESS, COMPLETED, "backlog", "abandoned"]),
                         Item.progress_current),
                        else_=None,
                    )
                ),
                0,
            ),
        ).where(Item.user_id == user.id, Item.type == ItemType.GAME.value),
    )
    return {"total": row[0], "via_steam": row[1], "hours_played": float(row[2])}


def _music_tile(db, user) -> dict:
    """Carrier split, not format split: a record collection is read by what
    it sits on (vinyl vs CD), and every vinyl size shares the "Vinyl" prefix."""
    row = _one(
        db,
        select(
            func.count(),
            func.count().filter(text("metadata->>'media' LIKE 'Vinyl%'")),
            func.count().filter(text("metadata->>'media' = 'CD'")),
        ).where(Item.user_id == user.id, Item.type == ItemType.MUSIC.value),
    )
    return {"total": row[0], "vinyl": row[1], "cd": row[2]}


def _value_tile(db, user) -> dict:
    month_start = datetime.now(UTC).date().replace(day=1)
    dominant_currency = db.scalar(
        select(Item.currency)
        .where(Item.user_id == user.id, Item.currency.is_not(None))
        .group_by(Item.currency)
        .order_by(func.count().desc())
        .limit(1)
    )
    row = _one(
        db,
        select(
            func.coalesce(func.sum(Item.purchase_price), 0),
            func.coalesce(
                func.sum(Item.purchase_price).filter(Item.acquisition_date >= month_start), 0
            ),
        ).where(Item.user_id == user.id),
    )
    return {"total": str(row[0]), "this_month": str(row[1]), "currency": dominant_currency or "EUR"}


def _continue_list(db, user) -> list[dict]:
    items = db.scalars(
        select(Item)
        .where(Item.user_id == user.id, Item.status == IN_PROGRESS)
        .order_by(Item.updated_at.desc())
        .limit(5)
    ).all()
    out = []
    for item in items:
        pct = None
        if item.progress_current is not None and item.progress_total:
            pct = min(100, round(float(item.progress_current) / float(item.progress_total) * 100))
        out.append(
            {
                "id": str(item.id),
                "title": item.title,
                "type": item.type,
                "sub": _subtitle(item),
                "progress_current": _num(item.progress_current),
                "progress_total": _num(item.progress_total),
                "pct": pct,
            }
        )
    return out


def _active_loans(db, user) -> list[dict]:
    items = db.scalars(
        select(Item)
        .where(
            Item.user_id == user.id,
            Item.borrowed_by.is_not(None),
            Item.returned_date.is_(None),
        )
        .order_by(Item.loaned_date.desc().nullslast())
        .limit(6)
    ).all()
    return [
        {
            "id": str(i.id),
            "title": i.title,
            "borrowed_by": i.borrowed_by,
            "loaned_date": i.loaned_date.isoformat() if i.loaned_date else None,
        }
        for i in items
    ]


def _recent_activity(db, user) -> list[dict]:
    rows = db.execute(
        select(ActivityEvent, Item.title, Item.type)
        .join(Item, ActivityEvent.item_id == Item.id)
        .where(ActivityEvent.user_id == user.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(8)
    ).all()
    return [
        {
            "item_id": str(event.item_id),
            "title": title,
            "type": item_type,
            "event_type": event.event_type,
            "old_value": event.old_value,
            "new_value": event.new_value,
            "created_at": event.created_at.isoformat(),
        }
        for event, title, item_type in rows
    ]


def _subtitle(item: Item) -> str:
    meta = item.meta
    if item.type == ItemType.BOOK.value and meta.get("authors"):
        return str(meta["authors"][0])
    return str(
        item.platform
        or meta.get("director")
        or meta.get("developer")
        or meta.get("artist")
        or ""
    )


def _num(value) -> float | None:
    return None if value is None else float(value)
