import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import case, func, literal, or_, select, text
from sqlalchemy.orm import Session, aliased

from app.core import bundles
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
    RelinkIn,
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


#: Metadata fields naming whoever made the thing — one per type, all
#: searched together (see list_items). `authors` is a JSONB list; `->>` on
#: it yields the array's JSON text, which a substring match reads fine.
CREATOR_FIELDS = ("authors", "artist", "director", "developer")
#: Synopsis fields: matched too, but ranked below title and creator hits.
DESCRIPTION_FIELDS = ("description", "overview")


def _meta_match(fields: tuple[str, ...], q: str):
    """OR of substring matches across the given metadata fields."""
    return or_(*[Item.meta[field].astext.ilike(f"%{q}%") for field in fields])


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
    upcoming: Annotated[bool, Query()] = False,
    sort: Annotated[str, Query(pattern="^(added|title|rating|updated|release)$")] = "added",
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
    # Searching reaches three layers, in this order of interest: the title,
    # the people behind the item, then the synopsis ("Batman" should find
    # The Dark Knight). Creator fields are named per type but searched
    # together, so one box covers authors, artists, directors and studios.
    title_match = or_(
        Item.title.ilike(f"%{q}%"),
        text("title_tsv @@ plainto_tsquery('simple', :q)").bindparams(q=q),
    ) if q else None
    creator_match = _meta_match(CREATOR_FIELDS, q) if q else None
    if q:
        query = query.where(
            or_(title_match, creator_match, _meta_match(DESCRIPTION_FIELDS, q))
        )
    if upcoming:
        # Release dates are ISO strings, full ("2026-12-18") or partial
        # ("2026-09", "2027"). An item is upcoming while its release period
        # hasn't fully passed: compare against today truncated to the same
        # precision, so a year-only date stays upcoming all year.
        today = datetime.now(UTC).date().isoformat()
        release = Item.meta["release_date"].astext
        query = query.where(release >= func.substr(today, 1, func.length(release)))

    # Bundled copies collapse to one row. The window runs after the filters,
    # so the representative is picked among the copies that actually match:
    # filtering on PC surfaces the PC copy even when another one fronts the
    # bundle. Unbundled items partition on their own id, i.e. stay as they are.
    rank = func.row_number().over(
        partition_by=func.coalesce(Item.bundle_id, Item.id),
        order_by=(Item.bundle_front.desc(), Item.created_at.asc(), Item.id.asc()),
    ).label("bundle_rank")
    # Tiering search hits has to happen inside the same SELECT as the window,
    # so it travels along as a column instead of an ORDER BY expression.
    tier = (
        case((title_match, 0), (creator_match, 1), else_=2) if q else literal(0)
    ).label("match_tier")
    inner = query.add_columns(tier, rank).subquery()
    Copy = aliased(Item, inner)
    collapsed = select(Copy).where(inner.c.bundle_rank == 1)

    total = db.scalar(select(func.count()).select_from(collapsed.subquery())) or 0

    order = {
        "added": Copy.created_at.desc(),
        "title": func.lower(Copy.title).asc(),
        "rating": Copy.rating.desc().nullslast(),
        "updated": Copy.updated_at.desc(),
        # Lexicographic asc puts partial dates at the start of their period
        # ("2027" < "2027-01-01"), matching how the Upcoming page groups.
        "release": Copy.meta["release_date"].astext.asc().nullslast(),
    }[sort]
    # id tiebreaker: batch imports share created_at, and without a total
    # order Postgres pages tied rows arbitrarily (duplicates/gaps in the UI).
    ordering = [order, Copy.id.desc()]
    if q:
        # Tier before the chosen sort, so "sort by title" still lists the
        # title matches first.
        ordering.insert(0, inner.c.match_tier)
    items = db.scalars(collapsed.order_by(*ordering).limit(limit).offset(offset)).all()
    return ItemListOut(items=bundles.as_out(db, user.id, items), total=total)


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemOut:
    item = _get_owned_item(db, user, item_id)
    return bundles.as_out(db, user.id, [item])[0]


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
    bundle_id = item.bundle_id
    db.delete(item)  # activity events cascade with the item
    db.flush()
    # A deleted copy leaves its bundle like an unbundled one would: the
    # remaining copies keep a front, and a lone survivor keeps no bundle.
    bundles.settle(db, user.id, bundle_id)
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


@router.post("/{item_id}/relink", response_model=ItemOut)
def relink_item(
    item_id: uuid.UUID,
    body: RelinkIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Item:
    """Point an item at a different catalog record — the fix for wrong
    or missing automatic matches. Provider metadata is replaced; import
    provenance, playtime and the user's title survive; cover and artwork
    refetch for the new record."""
    from app.providers import get_provider

    item = _get_owned_item(db, user, item_id)
    provider = get_provider(ItemType(item.type), db)
    if not provider.available:
        raise HTTPException(status_code=503, detail=f"{provider.name} is not configured")
    result = provider.details(body.external_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No catalog entry found for that id")

    preserved = (
        "psn_title_id", "epic_app_name", "gog_product_id", "steam_appid",
        "storefront", "platform", "playtime_minutes", "subscription",
    )
    meta = dict(result.metadata)
    if "platform" not in item.meta:
        # Search results join every platform into one display string;
        # never let that become a platform record.
        meta.pop("platform", None)
    for key in preserved:
        if key in item.meta:
            meta[key] = item.meta[key]
    if result.cover_url:
        item.cover_path = download_cover(result.cover_url, item.id)
        meta["cover_source_url"] = result.cover_url
    item.meta = meta  # stale artwork/description fields drop with the swap
    _link_platform(db, item)
    db.commit()

    fetch_artwork(db, item)  # hero/screenshots for the new record (commits)
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
