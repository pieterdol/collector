"""Bundling endpoints: group the copies of one release, or split them up.

The library grid shows one entry per bundle (see api/items.list_items); these
routes decide what a bundle contains and which copy fronts it. The rules
themselves live in core/bundles.py.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.items import _get_owned_item
from app.core import bundles
from app.core.security import get_current_user
from app.db import get_db
from app.models import Item, User
from app.schemas.item import BundleIn, CopyListOut, ItemOut

router = APIRouter(prefix="/api/items", tags=["bundles"])


@router.get("/{item_id}/copies", response_model=CopyListOut)
def list_copies(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CopyListOut:
    item = _get_owned_item(db, user, item_id)
    if item.bundle_id is None:
        return CopyListOut(copies=[])
    copies = bundles.members(db, user.id, item.bundle_id)
    return CopyListOut(copies=bundles.as_out(db, user.id, copies))


@router.post("/{item_id}/bundle", response_model=CopyListOut)
def bundle_items(
    item_id: uuid.UUID,
    body: BundleIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CopyListOut:
    """Pull other copies into this item's bundle (creating it if needed)."""
    item = _get_owned_item(db, user, item_id)
    targets = _owned_targets(db, user, item, body.item_ids)

    bundle_id = bundles.join(db, item, targets)
    db.commit()
    return CopyListOut(
        copies=bundles.as_out(db, user.id, bundles.members(db, user.id, bundle_id))
    )


@router.delete("/{item_id}/bundle", status_code=204)
def unbundle_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Take this copy out of its bundle; the last one left keeps no bundle."""
    item = _get_owned_item(db, user, item_id)
    if item.bundle_id is None:
        raise HTTPException(status_code=400, detail="This item is not bundled")
    bundles.leave(db, item)
    db.commit()


@router.post("/{item_id}/bundle/front", response_model=ItemOut)
def front_copy(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemOut:
    """Show this copy in the library instead of its siblings."""
    item = _get_owned_item(db, user, item_id)
    if item.bundle_id is None:
        raise HTTPException(status_code=400, detail="This item is not bundled")
    bundles.set_front(db, item)
    db.commit()
    db.refresh(item)
    return bundles.as_out(db, user.id, [item])[0]


def _owned_targets(db: Session, user: User, item: Item, ids: list[uuid.UUID]) -> list[Item]:
    """The requested copies, checked for ownership and type."""
    wanted = list(dict.fromkeys(ids))
    if item.id in wanted:
        raise HTTPException(status_code=400, detail="An item cannot be bundled with itself")
    found = {
        target.id: target
        for target in db.scalars(
            select(Item).where(Item.user_id == user.id, Item.id.in_(wanted))
        )
    }
    missing = [str(i) for i in wanted if i not in found]
    if missing:
        raise HTTPException(status_code=404, detail="Item not found")
    targets = [found[i] for i in wanted]
    if any(target.type != item.type for target in targets):
        raise HTTPException(
            status_code=400, detail="Only copies of the same type can be bundled"
        )
    return targets
