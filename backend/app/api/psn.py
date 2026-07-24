"""PSN library import — NPSSO paste-once flow, PS Plus filtered by default.

Large libraries take minutes and Sony's "purchases" include non-games
(companion apps, demos, media apps), so the import runs as a reviewed
background job: POST starts it, the job pauses in "review" with the
candidate and auto-excluded lists, and POST /confirm creates the items
the user actually selected.
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
from app.providers.psn import PsnError, exchange_npsso, played_titles, purchased_games
from app.schemas.psn import PsnConfirmIn, PsnJobOut, PsnJobStartOut

router = APIRouter(prefix="/api/psn", tags=["psn"])

# PSN platform tags → IGDB platform names (the platforms table's spelling).
_PLATFORM_NAMES = {
    "PS5": "PlayStation 5",
    "PS4": "PlayStation 4",
    "PS3": "PlayStation 3",
    "PSVITA": "PlayStation Vita",
    "PSP": "PlayStation Portable",
}

# Sony sells everything as an entitlement; these mark the non-games. The
# review step shows every exclusion, so false positives are rescuable.
_EXTRA_PATTERN = re.compile(
    r"\b(demo|beta|alpha|playtest|trial|network test|technical test|server test|"
    r"character creator|soundtrack|dynamic theme|avatar|benchmark|companion app|"
    r"media player)\b",
    re.IGNORECASE,
)
_MEDIA_APPS = {
    "prime video", "amazon prime video", "netflix", "youtube", "twitch",
    "spotify", "disney+", "crunchyroll", "hulu", "plex", "apple tv",
    "wwe network", "hbo max", "paramount+", "pluto tv", "tubi", "funimation",
    "vlc", "now tv", "videostream",
    # Dutch storefront names.
    "mediaspeler", "nlziet",
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
    """Kick off a PSN import job; poll GET /import/{job_id} for progress.
    The job pauses in status "review" until /confirm selects the titles."""
    job_id = import_jobs.create(owner_id=user.id)
    background.add_task(_prepare_review, job_id, user.id, body)
    return PsnJobStartOut(job_id=job_id)


@router.get("/import/{job_id}", response_model=PsnJobOut)
def import_status(
    job_id: str,
    user: User = Depends(get_current_user),
) -> PsnJobOut:
    job = _owned_job(job_id, user)
    return PsnJobOut(**{k: v for k, v in job.items() if not k.startswith("_") and k != "owner_id"})


@router.post("/import/{job_id}/confirm", response_model=PsnJobStartOut, status_code=202)
def confirm_import(
    job_id: str,
    body: PsnConfirmIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> PsnJobStartOut:
    """Create items for the selected title ids of a job in review."""
    job = _owned_job(job_id, user)
    if job["status"] != "review":
        raise HTTPException(status_code=409, detail="This import is not awaiting review")
    import_jobs.update(job_id, status="running", phase="Adding games")
    background.add_task(_create_items, job_id, user.id, body.title_ids)
    return PsnJobStartOut(job_id=job_id)


def _owned_job(job_id: str, user: User) -> dict:
    job = import_jobs.get(job_id)
    if job is None or job["owner_id"] != user.id:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


def _prepare_review(job_id: str, user_id: uuid.UUID, body: PsnImportIn) -> None:
    """Fetch and classify everything, then wait for the user's selection.

    PS Plus-gated claims are excluded up front unless include_ps_plus is
    set; when included they carry metadata.subscription = "PS Plus" so
    they stay identifiable if the subscription ever lapses.
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
        played = played_titles(token)  # best-effort; {} on failure
    except PsnError as err:
        import_jobs.fail(job_id, err.detail)
        return
    except httpx.HTTPError:
        import_jobs.fail(job_id, "PSN is unreachable right now")
        return

    # Titles already on the shelf (any format/source) get pre-excluded in
    # the review — imported earlier, added manually, whatever. Rescuable.
    with SessionLocal() as db:
        owned_names = {
            _name_key(title)
            for title in db.scalars(
                select(Item.title).where(
                    Item.user_id == user_id, Item.type == ItemType.GAME.value
                )
            )
        }

    candidates: list[dict] = []
    excluded: list[dict] = []
    raw_by_id: dict[str, dict] = {}
    ps5_names = {
        _name_key(game["name"])
        for game in games
        if game.get("platform") == "PS5" and game.get("name")
    }
    for game in games:
        title_id = str(game.get("titleId") or "").split("_")[0]
        name = game.get("name")
        if not title_id or not name or title_id in raw_by_id:
            continue
        raw_by_id[title_id] = game
        entry = {
            "title_id": title_id,
            "name": name,
            "platform": game.get("platform"),
            "subscription": game.get("subscription"),
        }
        reason = _classify(game, played.get(title_id, {}))
        if reason is None and _name_key(name) in owned_names:
            reason = "already in your collection"
        if reason is None and body.dedupe_cross_gen and game.get("platform") == "PS4":
            if _name_key(name) in ps5_names:
                reason = "PS4 version of a game you also own on PS5"
        if reason:
            excluded.append({**entry, "reason": reason})
        else:
            candidates.append(entry)

    import_jobs.update(
        job_id,
        status="review",
        phase="Waiting for review",
        done=0,
        total=0,
        candidates=candidates,
        excluded=excluded,
        _games=raw_by_id,
        _played=played,
    )


def _classify(game: dict, played: dict) -> str | None:
    """Reason to auto-exclude this entitlement, or None for a real game."""
    name = str(game.get("name") or "")
    if _name_key(name) in _MEDIA_APPS:
        return "media app"
    category = played.get("category")
    if isinstance(category, str) and "game" not in category:
        return "app, not a game (PSN category)"
    match = _EXTRA_PATTERN.search(name)
    if match:
        return f'name contains "{match.group(1)}"'
    return None


def _name_key(name: str) -> str:
    return re.sub(r"[™®]", "", name).casefold().strip()


def _create_items(job_id: str, user_id: uuid.UUID, title_ids: list[str]) -> None:
    """Import the selected titles (runs outside the request, own session)."""
    job = import_jobs.get(job_id) or {}
    raw_by_id: dict[str, dict] = job.get("_games") or {}
    played: dict[str, dict] = job.get("_played") or {}
    selected = [tid for tid in dict.fromkeys(title_ids) if tid in raw_by_id]

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
        for index, title_id in enumerate(selected):
            if index % 25 == 0:
                import_jobs.update(
                    job_id, phase="Adding games", done=index, total=len(selected)
                )
            if title_id in existing:
                continue
            existing.add(title_id)
            game = raw_by_id[title_id]

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
            minutes = (played.get(title_id) or {}).get("minutes", 0)
            if minutes:
                meta["playtime_minutes"] = minutes

            item = Item(
                user_id=user_id,
                type=ItemType.GAME.value,
                format=ItemFormat.DIGITAL.value,
                status=ItemStatus.BACKLOG.value,
                platform_id=platforms[platform_name],
                title=str(game.get("name")),
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

    import_jobs.finish(
        job_id,
        imported=len(imported_ids),
        skipped=len(selected) - len(imported_ids),
        total=len(selected),
    )
    # Clear review payloads and keep the registry lean.
    import_jobs.update(job_id, candidates=None, excluded=None, _games=None, _played=None)
    # Covers continue after the job reports done — posters fill in shortly.
    if imported_ids:
        fetch_covers(imported_ids)
