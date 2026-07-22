import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.artwork import fetch_artwork
from app.core.covers import download_cover
from app.core.events import record_event
from app.core.platforms import find_or_create_platform
from app.core.seasons import create_seasons_from_metadata
from app.core.security import get_current_user
from app.db import get_db
from app.domain.enums import EventType, ItemFormat, ItemStatus, ItemType
from app.models import ActivityEvent, Item, ItemSeason, User
from app.schemas.item import (
    AcquireIn,
    ActivityListOut,
    ItemCreate,
    ItemListOut,
    ItemOut,
    ItemUpdate,
)

router = APIRouter(prefix="/api/items", tags=["items"])


def _jsonable(value) -> str | None:
    """Decimals/dates → strings, so event payloads are JSON-safe."""
    return None if value is None else str(value)


def _get_owned_item(db: Session, user: User, item_id: uuid.UUID) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _link_platform(db: Session, item: Item) -> None:
    """Keep the platform FK in sync with metadata.platform (games only)."""
    if item.type != "game":
        return
    name = item.meta.get("platform")
    if not isinstance(name, str) or not name.strip():
        return
    if item.platform_ref is not None and item.platform_ref.name.lower() == name.strip().lower():
        return
    item.platform_id = find_or_create_platform(db, name).id


@router.post("", response_model=ItemOut, status_code=201)
def create_item(
    body: ItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Item:
    item = Item(
        user_id=user.id,
        type=body.type.value,
        format=body.format.value if body.format else None,
        status=body.status.value,
        title=body.title,
        meta=body.metadata,
        progress_current=body.progress_current,
        progress_total=body.progress_total,
        rating=body.rating,
        review=body.review,
        purchase_price=body.purchase_price,
        currency=body.currency,
        acquisition_date=body.acquisition_date,
    )
    if item.status == ItemStatus.COMPLETED.value:
        item.completed_at = datetime.now(UTC)
    _link_platform(db, item)
    db.add(item)
    db.flush()  # assign item.id before recording the event
    if body.cover_url:
        # Fetched once, stored locally; the item saves fine without it.
        item.cover_path = download_cover(body.cover_url, item.id)
        item.meta = {**item.meta, "cover_source_url": body.cover_url}
    create_seasons_from_metadata(db, item)  # TV: metadata.seasons → rows
    record_event(
        db,
        item_id=item.id,
        user_id=user.id,
        event_type=EventType.ITEM_ADDED,
        new_value={"status": item.status, "type": item.type, "title": item.title},
    )
    db.commit()
    return item


@router.get("/platforms")
def list_platforms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Distinct platforms across the user's games, for the library filter."""
    from app.models import Platform

    rows = db.scalars(
        select(Platform.name)
        .join(Item, Item.platform_id == Platform.id)
        .where(
            Item.user_id == user.id,
            Item.type == "game",
            # The library lists owned games; wishlist-only platforms would
            # produce empty filter results there.
            Item.status != ItemStatus.WISHLIST.value,
        )
        .distinct()
        .order_by(Platform.name)
    ).all()
    return {"platforms": list(rows)}


@router.get("", response_model=ItemListOut)
def list_items(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    type: Annotated[list[ItemType] | None, Query()] = None,
    format: Annotated[ItemFormat | None, Query()] = None,
    status: Annotated[list[ItemStatus] | None, Query()] = None,
    platform: Annotated[str | None, Query(max_length=100)] = None,
    media: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str, Query(pattern="^(added|title|rating|updated)$")] = "added",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ItemListOut:
    query = select(Item).where(Item.user_id == user.id)

    if type:
        query = query.where(Item.type.in_([t.value for t in type]))
    if format:
        query = query.where(Item.format == format.value)
    if status:
        query = query.where(Item.status.in_([s.value for s in status]))
    if platform:
        from app.models import Platform

        query = query.where(
            Item.platform_id.in_(select(Platform.id).where(Platform.name == platform))
        )
    if media:
        # Disc format of physical movies/TV (metadata.media), or of any
        # tracked TV season.
        query = query.where(
            or_(
                Item.meta["media"].astext == media,
                Item.id.in_(select(ItemSeason.item_id).where(ItemSeason.media == media)),
            )
        )
    if q:
        query = query.where(
            or_(
                Item.title.ilike(f"%{q}%"),
                text("title_tsv @@ plainto_tsquery('simple', :q)").bindparams(q=q),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    order = {
        "added": Item.created_at.desc(),
        "title": func.lower(Item.title).asc(),
        "rating": Item.rating.desc().nullslast(),
        "updated": Item.updated_at.desc(),
    }[sort]
    # id tiebreaker: batch imports share created_at, and without a total
    # order Postgres pages tied rows arbitrarily (duplicates/gaps in the UI).
    items = db.scalars(query.order_by(order, Item.id.desc()).limit(limit).offset(offset)).all()
    return ItemListOut(items=[ItemOut.model_validate(i) for i in items], total=total)


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Item:
    return _get_owned_item(db, user, item_id)


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID,
    body: ItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Item:
    item = _get_owned_item(db, user, item_id)
    fields = body.model_dump(exclude_unset=True)
    cover_url = fields.pop("cover_url", None)
    if cover_url:
        item.cover_path = download_cover(cover_url, item.id)
        item.meta = {**item.meta, "cover_source_url": cover_url}

    _apply_status_change(db, item, user, fields)
    _apply_progress_change(db, item, user, fields)
    _apply_rating_change(db, item, user, fields)
    _apply_loan_changes(db, item, user, fields)

    if "metadata" in fields:
        item.meta = fields.pop("metadata")
        _link_platform(db, item)
    for name, value in fields.items():
        setattr(item, name, value.value if hasattr(value, "value") else value)

    db.commit()
    db.refresh(item)
    return item


def _apply_status_change(db, item, user, fields) -> None:
    if "status" not in fields:
        return
    new_status = fields.pop("status").value
    if new_status == item.status:
        return
    record_event(
        db,
        item_id=item.id,
        user_id=user.id,
        event_type=EventType.STATUS_CHANGE,
        old_value={"status": item.status},
        new_value={"status": new_status},
    )
    item.status = new_status
    item.completed_at = (
        datetime.now(UTC) if new_status == ItemStatus.COMPLETED.value else None
    )


def _apply_progress_change(db, item, user, fields) -> None:
    if "progress_current" not in fields and "progress_total" not in fields:
        return
    new_current = (
        fields.pop("progress_current") if "progress_current" in fields else item.progress_current
    )
    new_total = (
        fields.pop("progress_total") if "progress_total" in fields else item.progress_total
    )
    if new_current == item.progress_current and new_total == item.progress_total:
        return  # no-op PATCH: don't pollute the activity log
    old = {
        "progress_current": _jsonable(item.progress_current),
        "progress_total": _jsonable(item.progress_total),
    }
    item.progress_current = new_current
    item.progress_total = new_total
    record_event(
        db,
        item_id=item.id,
        user_id=user.id,
        event_type=EventType.PROGRESS_UPDATE,
        old_value=old,
        new_value={
            "progress_current": _jsonable(item.progress_current),
            "progress_total": _jsonable(item.progress_total),
        },
    )


def _apply_rating_change(db, item, user, fields) -> None:
    if "rating" not in fields:
        return
    new_rating = fields.pop("rating")
    record_event(
        db,
        item_id=item.id,
        user_id=user.id,
        event_type=EventType.RATING_SET,
        old_value={"rating": _jsonable(item.rating)},
        new_value={"rating": _jsonable(new_rating)},
    )
    item.rating = new_rating


def _apply_loan_changes(db, item, user, fields) -> None:
    if "borrowed_by" in fields and fields["borrowed_by"] and not item.borrowed_by:
        record_event(
            db,
            item_id=item.id,
            user_id=user.id,
            event_type=EventType.LOAN_OUT,
            new_value={
                "borrowed_by": fields["borrowed_by"],
                "loaned_date": _jsonable(fields.get("loaned_date")),
            },
        )
    if "returned_date" in fields and fields["returned_date"] and not item.returned_date:
        record_event(
            db,
            item_id=item.id,
            user_id=user.id,
            event_type=EventType.LOAN_RETURN,
            old_value={"borrowed_by": item.borrowed_by},
            new_value={"returned_date": _jsonable(fields["returned_date"])},
        )


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    item = _get_owned_item(db, user, item_id)
    db.delete(item)  # activity events cascade with the item
    db.commit()


@router.post("/{item_id}/acquire", response_model=ItemOut)
def acquire_item(
    item_id: uuid.UUID,
    body: AcquireIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Item:
    """Wishlist → owned: set format/price/date, move to backlog, log it."""
    item = _get_owned_item(db, user, item_id)
    if item.status != ItemStatus.WISHLIST.value:
        raise HTTPException(status_code=400, detail="Only wishlist items can be acquired")

    old_status = item.status
    item.status = ItemStatus.BACKLOG.value
    item.format = body.format.value
    item.purchase_price = body.purchase_price
    item.currency = body.currency
    item.acquisition_date = body.acquisition_date
    if body.platform and item.type == "game":
        item.meta = {**item.meta, "platform": body.platform}
        _link_platform(db, item)

    record_event(
        db,
        item_id=item.id,
        user_id=user.id,
        event_type=EventType.ACQUIRED,
        old_value={"status": old_status},
        new_value={
            "status": item.status,
            "format": item.format,
            "purchase_price": _jsonable(item.purchase_price),
            "acquisition_date": _jsonable(item.acquisition_date),
        },
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/cover", response_model=ItemOut)
async def upload_cover(
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Item:
    """Set a custom cover from an uploaded image (e.g. a photo of the box).

    The file gets a fresh random-suffixed name so replaced covers never
    fight browser or service-worker caches; old files are removed.
    """
    from pathlib import Path

    from app.config import get_settings
    from app.core.covers import _EXTENSIONS, MAX_BYTES

    item = _get_owned_item(db, user, item_id)
    extension = _EXTENSIONS.get((file.content_type or "").split(";")[0].strip())
    if extension is None:
        raise HTTPException(status_code=415, detail="Use a JPEG, PNG or WebP image")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large (max 5 MB)")

    covers_dir = Path(get_settings().media_dir) / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    for old in covers_dir.glob(f"{item.id}*"):
        old.unlink(missing_ok=True)
    name = f"{item.id}-{uuid.uuid4().hex[:8]}{extension}"
    (covers_dir / name).write_bytes(content)
    item.cover_path = f"/media/covers/{name}"
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/artwork", response_model=ItemOut)
def fetch_item_artwork(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Item:
    """Fetch hero art, screenshots and description once (idempotent)."""
    item = _get_owned_item(db, user, item_id)
    fetch_artwork(db, item)
    db.refresh(item)
    return item


@router.delete("/{item_id}/activity/{event_id}", status_code=204)
def delete_activity_event(
    item_id: uuid.UUID,
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Remove one history entry (user-requested cleanup of the log)."""
    item = _get_owned_item(db, user, item_id)
    event = db.get(ActivityEvent, event_id)
    if event is None or event.item_id != item.id:
        raise HTTPException(status_code=404, detail="Activity entry not found")
    db.delete(event)
    db.commit()


@router.get("/{item_id}/activity", response_model=ActivityListOut)
def item_activity(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ActivityListOut:
    item = _get_owned_item(db, user, item_id)
    events = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.item_id == item.id)
        .order_by(ActivityEvent.created_at.desc())
    ).all()
    return ActivityListOut(events=events)
