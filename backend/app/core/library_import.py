"""Shared core for storefront library-file imports (Epic, GOG).

Neither store has a usable public API, so we import the library files the
user's launcher already maintains: Heroic's store caches
(store_cache/legendary_library.json, gog_library.json) and legendary's
`list --json` dumps. Each store's router supplies a StoreSpec; everything
else — parsing, DLC/runner filtering, dedupe, item + event creation,
cover fetching — is identical.
"""

import json
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.covers import download_cover
from app.core.events import record_event
from app.core.platforms import find_or_create_platform
from app.db import SessionLocal
from app.domain.enums import EventType, ItemFormat, ItemStatus, ItemType
from app.models import Item, User

MAX_BYTES = 40 * 1024 * 1024  # legendary dumps carry full catalog metadata

# Poster-shaped art first; Heroic's square art beats no art.
_KEY_IMAGE_PREFERENCE = ["DieselGameBoxTall", "OfferImageTall", "DieselGameBox"]


@dataclass(frozen=True)
class StoreSpec:
    runner: str  # Heroic runner value ("legendary", "gog")
    id_key: str  # metadata key holding the store's game id
    storefront: str  # user-facing storefront name
    event_source: str  # activity-event source tag
    file_hint: str  # named in the 400 for unrecognized uploads


def import_library(
    db: Session, user: User, raw: bytes, spec: StoreSpec
) -> tuple[list[uuid.UUID], int]:
    """Create items for every new game in the file.

    Returns (imported item ids, total entries in the file); everything
    not imported — DLC, other runners, duplicates — counts as skipped.
    """
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max 40 MB)")
    entries = _parse_entries(raw, spec)

    existing = set(
        db.scalars(
            select(text(f"metadata->>'{spec.id_key}'")).select_from(Item).where(
                Item.user_id == user.id,
                Item.type == ItemType.GAME.value,
                text(f"metadata ? '{spec.id_key}'"),
            )
        )
    )

    pc_platform = find_or_create_platform(db, "PC (Microsoft Windows)")
    imported_ids: list[uuid.UUID] = []
    for entry in entries:
        game = _normalize(entry, spec)
        if game is None or game["app_name"] in existing:
            continue
        existing.add(game["app_name"])  # dedupe within the file too
        meta = {
            spec.id_key: game["app_name"],
            "storefront": spec.storefront,
            "platform": "PC (Microsoft Windows)",
        }
        if game["developer"]:
            meta["developer"] = game["developer"]
        if game["cover_url"]:
            meta["cover_source_url"] = game["cover_url"]
        item = Item(
            user_id=user.id,
            type=ItemType.GAME.value,
            format=ItemFormat.DIGITAL.value,
            status=ItemStatus.BACKLOG.value,
            platform_id=pc_platform.id,
            title=game["title"],
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
                       "source": spec.event_source},
        )
        imported_ids.append(item.id)
    db.commit()
    return imported_ids, len(entries)


def _parse_entries(raw: bytes, spec: StoreSpec) -> list[dict]:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="That file is not valid JSON")
    entries = None
    if isinstance(data, list):
        entries = data  # legendary list --json
    elif isinstance(data, dict):
        for key in ("library", "games"):  # Heroic caches, old and new
            if isinstance(data.get(key), list):
                entries = data[key]
                break
    if entries is None:
        raise HTTPException(
            status_code=400, detail=f"Unrecognized file. Upload {spec.file_hint}."
        )
    return [e for e in entries if isinstance(e, dict)]


def _normalize(entry: dict, spec: StoreSpec) -> dict | None:
    """One launcher entry → an importable game, or None for anything that
    isn't a game from this store (DLC, other runners, malformed rows)."""
    app_name = entry.get("app_name")
    if not isinstance(app_name, str) or not app_name:
        return None
    if entry.get("runner") not in (None, spec.runner):
        return None  # Heroic caches all its runners in the same shape
    meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    install = entry.get("install") if isinstance(entry.get("install"), dict) else {}
    if meta.get("mainGameItem") or install.get("is_dlc"):
        return None  # DLC
    title = entry.get("app_title") or entry.get("title") or meta.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    developer = entry.get("developer") or meta.get("developer")
    return {
        "app_name": app_name,
        "title": title.strip(),
        "developer": developer if isinstance(developer, str) else None,
        "cover_url": _cover_url(entry, meta),
    }


def _cover_url(entry: dict, meta: dict) -> str | None:
    images = meta.get("keyImages")
    if isinstance(images, list):
        by_type = {
            i.get("type"): i.get("url")
            for i in images
            if isinstance(i, dict) and isinstance(i.get("url"), str)
        }
        for kind in _KEY_IMAGE_PREFERENCE:
            if by_type.get(kind):
                return by_type[kind]
    for key in ("art_square", "art_cover"):  # Heroic fields
        url = entry.get(key)
        if isinstance(url, str) and url.startswith("http"):
            return url
    return None


def fetch_covers(item_ids: list[uuid.UUID]) -> None:
    """Download box art for freshly imported games (own session)."""
    with SessionLocal() as db:
        for item_id in item_ids:
            item = db.get(Item, item_id)
            if item is None or item.cover_path:
                continue
            url = item.meta.get("cover_source_url")
            if url:
                item.cover_path = download_cover(url, item.id)
                db.commit()
