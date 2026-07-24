"""PSN library import — NPSSO paste-once flow, PS Plus filtered by default.

Large libraries take minutes (Sony pagination + per-title work), which
outlives reverse-proxy timeouts, so the import runs as a background job:
POST starts it and returns a job id, GET polls progress.
"""

import re
import uuid
from decimal import Decimal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.core import import_jobs
from app.core.events import record_event
from app.core.library_import import fetch_covers
from app.core.platforms import find_or_create_platform
from app.core.security import get_current_user
from app.db import SessionLocal
from app.domain.enums import EventType, ItemFormat, ItemStatus, ItemType
from app.models import Item, User
from app.providers.psn import PsnError, exchange_npsso, play_durations, purchased_games
from app.schemas.psn import PsnJobOut, PsnJobStartOut

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
    # Same title on PS4 and PS5 → keep only the PS5 entry.
    dedupe_cross_gen: bool = False


@router.post("/import", response_model=PsnJobStartOut, status_code=202)
def start_import(
    body: PsnImportIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> PsnJobStartOut:
    """Kick off a PSN import job; poll GET /import/{job_id} for progress."""
    job_id = import_jobs.create(owner_id=user.id)
    background.add_task(_run_import, job_id, user.id, body)
    return PsnJobStartOut(job_id=job_id)


@router.get("/import/{job_id}", response_model=PsnJobOut)
def import_status(
    job_id: str,
    user: User = Depends(get_current_user),
) -> PsnJobOut:
    job = import_jobs.get(job_id)
    if job is None or job["owner_id"] != user.id:
        raise HTTPException(status_code=404, detail="Import job not found")
    return PsnJobOut(**{k: v for k, v in job.items() if k != "owner_id"})


def _run_import(job_id: str, user_id: uuid.UUID, body: PsnImportIn) -> None:
    """The actual import, running outside the request (own session).

    PS Plus-gated claims are excluded unless include_ps_plus is set;
    when included they carry metadata.subscription = "PS Plus" so they
    stay identifiable if the subscription ever lapses.
    """
    try:
        import_jobs.update(job_id, phase="Signing in to PlayStation Network")
        token = exchange_npsso(body.npsso)
        import_jobs.update(job_id, phase="Fetching purchased games")
        games = purchased_games(
            token,
            body.include_ps_plus,
            on_progress=lambda done, total: import_jobs.update(
                job_id, done=done, total=total
            ),
        )
        import_jobs.update(job_id, phase="Fetching playtime", done=0, total=0)
        durations = play_durations(token)  # best-effort; {} on failure
    except PsnError as err:
        import_jobs.fail(job_id, err.detail)
        return
    except httpx.HTTPError:
        import_jobs.fail(job_id, "PSN is unreachable right now")
        return

    if body.dedupe_cross_gen:
        games = _drop_older_gen_duplicates(games)

    with SessionLocal() as db:
        existing = set(
            db.scalars(
                select(text("metadata->>'psn_title_id'")).select_from(Item).where(
                    Item.user_id == user_id,
                    Item.type == ItemType.GAME.value,
                    text("metadata ? 'psn_title_id'"),
                )
            )
        )

        platforms: dict[str, uuid.UUID] = {}
        imported_ids: list[uuid.UUID] = []
        for index, game in enumerate(games):
            if index % 25 == 0:
                import_jobs.update(
                    job_id, phase="Adding games", done=index, total=len(games)
                )
            # Purchased-list ids carry a "_00" service suffix ("CUSA04692_00");
            # strip it so they match the playtime list and stay canonical.
            title_id = str(game.get("titleId") or "").split("_")[0]
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
            minutes = durations.get(title_id, 0)
            if minutes:
                meta["playtime_minutes"] = minutes

            item = Item(
                user_id=user_id,
                type=ItemType.GAME.value,
                format=ItemFormat.DIGITAL.value,
                status=ItemStatus.BACKLOG.value,
                platform_id=platforms[platform_name],
                title=title,
                meta=meta,
                # Playtime prefills progress in hours, like the Steam import.
                progress_current=round(Decimal(minutes) / 60, 1) if minutes else None,
            )
            db.add(item)
            db.flush()
            record_event(
                db,
                item_id=item.id,
                user_id=user_id,
                event_type=EventType.ITEM_ADDED,
                new_value={"status": item.status, "type": item.type, "title": item.title,
                           "source": "psn_import"},
            )
            imported_ids.append(item.id)
        db.commit()

    _finish(job_id, imported_ids, games)


def _drop_older_gen_duplicates(games: list[dict]) -> list[dict]:
    """Same title on PS4 and PS5 → keep the PS5 entry (opt-in).

    Sony's response carries no usable cross-gen key (conceptId is null),
    so this matches on the normalized title.
    """
    ps5_names = {
        _name_key(game["name"])
        for game in games
        if game.get("platform") == "PS5" and game.get("name")
    }
    return [
        game
        for game in games
        if not (
            game.get("platform") == "PS4"
            and _name_key(str(game.get("name") or "")) in ps5_names
        )
    ]


def _name_key(name: str) -> str:
    return re.sub(r"[™®]", "", name).casefold().strip()


def _finish(job_id: str, imported_ids: list[uuid.UUID], games: list[dict]) -> None:
    import_jobs.finish(
        job_id,
        imported=len(imported_ids),
        skipped=len(games) - len(imported_ids),
        total=len(games),
    )
    # Covers continue after the job reports done — posters fill in shortly.
    if imported_ids:
        fetch_covers(imported_ids)
