"""Shared core for storefront library-file imports (Epic, GOG).

Neither store has a usable public API, so we import the library files the
user's launcher already maintains: Heroic's store caches
(store_cache/legendary_library.json, gog_library.json) and legendary's
`list --json` dumps. Each store's router supplies a StoreSpec; everything
else — parsing, DLC/runner filtering, review classification, dedupe, item
and event creation, cover fetching — is identical.

Imports pause for review (same contract as PSN): the upload parses the
file and classifies every entry, then the user confirms which titles to
create.
"""

import json
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import import_jobs
from app.core.covers import download_cover
from app.core.events import record_event
from app.core.platforms import find_or_create_platform
from app.core.store_filters import classify, name_key, owned_verdict
from app.db import SessionLocal
from app.domain.enums import EventType, ItemFormat, ItemStatus, ItemType
from app.models import Item, User

MAX_BYTES = 40 * 1024 * 1024  # legendary dumps carry full catalog metadata

# Epic and GOG are PC storefronts; every import lands on this platform.
PC_PLATFORM = "PC (Microsoft Windows)"

# Poster-shaped art first; Heroic's square art beats no art.
_KEY_IMAGE_PREFERENCE = ["DieselGameBoxTall", "OfferImageTall", "DieselGameBox"]


@dataclass(frozen=True)
class StoreSpec:
    runner: str  # Heroic runner value ("legendary", "gog")
    id_key: str  # metadata key holding the store's game id
    storefront: str  # user-facing storefront name
    event_source: str  # activity-event source tag
    file_hint: str  # named in the 400 for unrecognized uploads


def parse_upload(raw: bytes, spec: StoreSpec) -> list[dict]:
    """Validate the uploaded file synchronously, so a bad file 400s."""
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max 40 MB)")
    return _parse_entries(raw, spec)


def prepare_review(
    job_id: str, user_id: uuid.UUID, entries: list[dict], spec: StoreSpec
) -> None:
    """Classify every entry, then park the job until the user confirms."""
    import_jobs.update(job_id, phase="Reading library file", total=len(entries))

    with SessionLocal() as db:
        # Title → the platforms it's already owned on, so a PC copy of a
        # game owned on a console isn't mistaken for a duplicate.
        owned: dict[str, set[str | None]] = {}
        for item in db.scalars(
            select(Item).where(
                Item.user_id == user_id, Item.type == ItemType.GAME.value
            )
        ):
            owned.setdefault(name_key(item.title), set()).add(item.platform)
        already_imported = set(
            db.scalars(
                select(text(f"metadata->>'{spec.id_key}'")).select_from(Item).where(
                    Item.user_id == user_id,
                    Item.type == ItemType.GAME.value,
                    text(f"metadata ? '{spec.id_key}'"),
                )
            )
        )

    candidates: list[dict] = []
    excluded: list[dict] = []
    games: dict[str, dict] = {}
    for entry in entries:
        game = _normalize(entry, spec)
        if game is None or game["app_name"] in games:
            continue  # DLC, other runners, malformed rows: not library items
        games[game["app_name"]] = game
        row = {"title_id": game["app_name"], "name": game["title"], "platform": "PC"}
        reason = classify(game["title"])
        note = None
        if reason is None:
            if game["app_name"] in already_imported:
                reason = "already in your collection"
            else:
                reason, note = owned_verdict(game["title"], PC_PLATFORM, owned)
        if reason:
            excluded.append({**row, "reason": reason})
        else:
            candidates.append({**row, "note": note})

    import_jobs.update(
        job_id,
        status="review",
        phase="Waiting for review",
        done=0,
        total=0,
        candidates=candidates,
        excluded=excluded,
        _games=games,
    )


def import_selected(
    job_id: str, user_id: uuid.UUID, title_ids: list[str], spec: StoreSpec
) -> None:
    """Create items for the confirmed selection (own session)."""
    job = import_jobs.get(job_id) or {}
    games: dict[str, dict] = job.get("_games") or {}
    selected = [tid for tid in dict.fromkeys(title_ids) if tid in games]

    with SessionLocal() as db:
        existing = set(
            db.scalars(
                select(text(f"metadata->>'{spec.id_key}'")).select_from(Item).where(
                    Item.user_id == user_id,
                    Item.type == ItemType.GAME.value,
                    text(f"metadata ? '{spec.id_key}'"),
                )
            )
        )

        pc_platform = find_or_create_platform(db, PC_PLATFORM)
        imported_ids: list[uuid.UUID] = []
        for index, title_id in enumerate(selected):
            if index % 25 == 0:
                import_jobs.update(
                    job_id, phase="Adding games", done=index, total=len(selected)
                )
            if title_id in existing:
                continue
            existing.add(title_id)
            game = games[title_id]

            meta = {
                spec.id_key: title_id,
                "storefront": spec.storefront,
                "platform": PC_PLATFORM,
            }
            if game["developer"]:
                meta["developer"] = game["developer"]
            if game["cover_url"]:
                meta["cover_source_url"] = game["cover_url"]
            item = Item(
                user_id=user_id,
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
                user_id=user_id,
                event_type=EventType.ITEM_ADDED,
                new_value={"status": item.status, "type": item.type, "title": item.title,
                           "source": spec.event_source},
            )
            imported_ids.append(item.id)
        db.commit()

    import_jobs.finish(
        job_id,
        imported=len(imported_ids),
        skipped=len(selected) - len(imported_ids),
        total=len(selected),
    )
    import_jobs.update(job_id, candidates=None, excluded=None, _games=None)
    if imported_ids:
        fetch_covers(imported_ids)


def _parse_entries(raw: bytes, spec: StoreSpec) -> list[dict]:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="That file is not valid JSON")
    entries = None
    if isinstance(data, list):
        entries = data  # legendary list --json
    elif isinstance(data, dict):
        for key in ("library", "games"):  # Heroic caches, new and old
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
