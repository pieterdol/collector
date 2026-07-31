"""Bundling copies of the same release under one library entry.

A bundle is an opaque group id shared by items (`items.bundle_id`); the copy
with `bundle_front` is the one the library grid shows. Every function here
records its activity events in the caller's transaction and leaves the commit
to the caller.

Invariants this module keeps:
- a bundle has at least two members (a lone member is dissolved),
- exactly one member fronts it (removing the front promotes another),
- all members share a user and a type (enforced when they join).
"""

import uuid
from dataclasses import dataclass, field
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import record_event
from app.domain.enums import EventType
from app.models import Item
from app.schemas.item import ItemOut

#: Labels shown under a collapsed bundle ("PS5 · PC"); more would not fit.
MAX_LABELS = 4


def members(db: Session, user_id: uuid.UUID, bundle_id: uuid.UUID) -> list[Item]:
    """Every copy in a bundle, the front one first, then oldest to newest."""
    return list(
        db.scalars(
            select(Item)
            .where(Item.user_id == user_id, Item.bundle_id == bundle_id)
            .order_by(Item.bundle_front.desc(), Item.created_at.asc(), Item.id.asc())
        )
    )


def join(db: Session, anchor: Item, targets: Sequence[Item]) -> uuid.UUID:
    """Bundle `targets` with `anchor`, creating the bundle if it's new.

    A target that already belongs to another bundle brings that bundle's
    other copies along — bundling two bundles merges them rather than
    stranding half a group.
    """
    bundle_id = anchor.bundle_id or uuid.uuid4()
    joining: list[Item] = []
    for target in targets:
        if target.bundle_id == bundle_id:
            continue  # already in this bundle
        if target.bundle_id is None:
            joining.append(target)
        else:
            joining.extend(members(db, target.user_id, target.bundle_id))
    if not joining:
        return bundle_id

    if anchor.bundle_id is None:
        anchor.bundle_id = bundle_id
        anchor.bundle_front = True
        _log_bundled(db, anchor, bundle_id, with_title=joining[0].title)
    for item in joining:
        item.bundle_id = bundle_id
        item.bundle_front = False
        _log_bundled(db, item, bundle_id, with_title=anchor.title)
    return bundle_id


def leave(db: Session, item: Item) -> None:
    """Take one copy out of its bundle and settle what's left behind."""
    bundle_id = item.bundle_id
    was_front = item.bundle_front
    item.bundle_id = None
    item.bundle_front = False
    record_event(
        db,
        item_id=item.id,
        user_id=item.user_id,
        event_type=EventType.UNBUNDLED,
        old_value={"bundle_id": str(bundle_id)},
    )
    db.flush()  # the unique front index sees a consistent bundle
    settle(db, item.user_id, bundle_id, promote=was_front)


def settle(
    db: Session, user_id: uuid.UUID, bundle_id: uuid.UUID | None, *, promote: bool = True
) -> None:
    """Restore the invariants after a copy left (or was deleted).

    One copy left means there is no bundle any more; a bundle without a front
    copy gets its oldest member promoted.
    """
    if bundle_id is None:
        return
    remaining = members(db, user_id, bundle_id)
    if len(remaining) <= 1:
        for item in remaining:
            item.bundle_id = None
            item.bundle_front = False
            record_event(
                db,
                item_id=item.id,
                user_id=user_id,
                event_type=EventType.UNBUNDLED,
                old_value={"bundle_id": str(bundle_id)},
            )
        return
    if promote and not any(item.bundle_front for item in remaining):
        front = remaining[0]
        front.bundle_front = True
        record_event(
            db,
            item_id=front.id,
            user_id=user_id,
            event_type=EventType.BUNDLE_FRONT,
            new_value={"front": True},
        )


def set_front(db: Session, item: Item) -> None:
    """Make this copy the one the library shows."""
    for other in members(db, item.user_id, item.bundle_id):
        if other.id == item.id or not other.bundle_front:
            continue
        other.bundle_front = False
        record_event(
            db,
            item_id=other.id,
            user_id=item.user_id,
            event_type=EventType.BUNDLE_FRONT,
            old_value={"front": True},
            new_value={"front": False},
        )
    db.flush()  # demote before promoting: one front per bundle
    item.bundle_front = True
    record_event(
        db,
        item_id=item.id,
        user_id=item.user_id,
        event_type=EventType.BUNDLE_FRONT,
        old_value={"front": False},
        new_value={"front": True},
    )


@dataclass
class Summary:
    """What a collapsed library entry says about the bundle behind it."""

    count: int = 0
    labels: list[str] = field(default_factory=list)


def summaries(
    db: Session, user_id: uuid.UUID, bundle_ids: set[uuid.UUID]
) -> dict[uuid.UUID, Summary]:
    """Copy count and distinguishing labels per bundle, for the grid badge."""
    if not bundle_ids:
        return {}
    rows = db.scalars(
        select(Item)
        .where(Item.user_id == user_id, Item.bundle_id.in_(bundle_ids))
        .order_by(Item.bundle_id, Item.bundle_front.desc(), Item.created_at.asc())
    ).all()
    out: dict[uuid.UUID, Summary] = {}
    for item in rows:
        summary = out.setdefault(item.bundle_id, Summary())
        summary.count += 1
        label = _label(item)
        if label and label not in summary.labels and len(summary.labels) < MAX_LABELS:
            summary.labels.append(label)
    return out


def as_out(db: Session, user_id: uuid.UUID, items: Sequence[Item]) -> list[ItemOut]:
    """Serialize items with their bundle count and labels filled in."""
    found = summaries(db, user_id, {i.bundle_id for i in items if i.bundle_id})
    result = []
    for item in items:
        out = ItemOut.model_validate(item)
        summary = found.get(item.bundle_id) if item.bundle_id else None
        if summary is not None:
            out.bundle_count = summary.count
            out.bundle_labels = summary.labels
        result.append(out)
    return result


def _label(item: Item) -> str | None:
    """What tells this copy apart from its siblings: platform, disc/carrier,
    else whether it's the physical or the digital one."""
    if item.type == "game" and item.platform:
        return item.platform
    media = item.meta.get("media")
    if isinstance(media, str) and media:
        return media
    return item.format.capitalize() if item.format else None


def _log_bundled(db: Session, item: Item, bundle_id: uuid.UUID, *, with_title: str) -> None:
    record_event(
        db,
        item_id=item.id,
        user_id=item.user_id,
        event_type=EventType.BUNDLED,
        new_value={"bundle_id": str(bundle_id), "with": with_title},
    )
