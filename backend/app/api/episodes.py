"""Per-episode watch state for a TV season.

Episode rows arrive lazily: the client POSTs /refresh when a season is
opened for the first time (?force=true re-asks TMDB for a running show).
Ticking one episode logs an episode_watched event; when that completes or
breaks the season, the derived season flag is logged too. The bulk
"mark the whole season" path lives in api/seasons.py and stays one event.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.items import _get_owned_item
from app.api.seasons import (
    _get_or_create_season,
    record_season_watched_event,
)
from app.core.episodes import fetch_season_episodes, sync_season_watched
from app.core.events import record_event
from app.core.security import get_current_user
from app.db import get_db
from app.domain.enums import EventType, ItemType
from app.models import ItemEpisode, ItemSeason, User
from app.providers import get_provider
from app.schemas.episode import EpisodeListOut, EpisodeOut, EpisodeUpdate

router = APIRouter(prefix="/api/items/{item_id}/seasons/{season_number}/episodes", tags=["episodes"])

SeasonNumber = Annotated[int, Path(ge=0)]
EpisodeNumber = Annotated[int, Path(ge=0)]


@router.get("", response_model=EpisodeListOut)
def list_episodes(
    item_id: uuid.UUID,
    season_number: SeasonNumber,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpisodeListOut:
    """Tracked episodes; empty until the season has been fetched once."""
    item = _get_owned_item(db, user, item_id)
    season = _find_season(db, item.id, season_number)
    return _episode_list(season)


@router.post("/refresh", response_model=EpisodeListOut)
def refresh_episodes(
    item_id: uuid.UUID,
    season_number: SeasonNumber,
    force: Annotated[bool, Query()] = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpisodeListOut:
    """Fetch this season's episodes from TMDB, keeping existing watch state."""
    item = _get_owned_item(db, user, item_id)
    if item.type != ItemType.TV.value:
        raise HTTPException(status_code=400, detail="Episodes apply to TV shows only")
    provider = get_provider(ItemType.TV, db)
    if not provider.available:
        raise HTTPException(status_code=503, detail=f"{provider.name} is not configured")
    if not item.meta.get("tmdb_id"):
        raise HTTPException(
            status_code=400, detail="This show has no TMDB match — re-link it to load episodes"
        )

    season = _get_or_create_season(db, item, season_number)
    was_watched = season.watched
    fetch_season_episodes(db, item, season, force=force)
    # A new episode on a fully watched season drops the season flag again.
    if sync_season_watched(season):
        record_season_watched_event(db, item, user, season, was_watched)
    db.commit()
    return _episode_list(season)


@router.patch("/{episode_number}", response_model=EpisodeOut)
def update_episode(
    item_id: uuid.UUID,
    season_number: SeasonNumber,
    episode_number: EpisodeNumber,
    body: EpisodeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemEpisode:
    item = _get_owned_item(db, user, item_id)
    season = _find_season(db, item.id, season_number)
    episode = next(
        (e for e in season.episodes if e.episode_number == episode_number), None
    ) if season else None
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    if episode.watched == body.watched:
        return episode  # no-op: no event, nothing to commit

    episode.watched = body.watched
    was_watched = season.watched
    record_event(
        db,
        item_id=item.id,
        user_id=user.id,
        event_type=EventType.EPISODE_WATCHED,
        old_value={
            "season_number": season.season_number,
            "episode_number": episode_number,
            "watched": not body.watched,
        },
        new_value={
            "season_number": season.season_number,
            "episode_number": episode_number,
            "watched": body.watched,
        },
    )
    if sync_season_watched(season):
        record_season_watched_event(db, item, user, season, was_watched)
    db.commit()
    db.refresh(episode)
    return episode


def _find_season(db: Session, item_id: uuid.UUID, season_number: int) -> ItemSeason | None:
    return db.scalar(
        select(ItemSeason).where(
            ItemSeason.item_id == item_id, ItemSeason.season_number == season_number
        )
    )


def _episode_list(season: ItemSeason | None) -> EpisodeListOut:
    episodes = season.episodes if season else []
    return EpisodeListOut(
        episodes=[EpisodeOut.model_validate(e) for e in episodes],
        total=len(episodes),
        watched=sum(1 for e in episodes if e.watched),
    )
