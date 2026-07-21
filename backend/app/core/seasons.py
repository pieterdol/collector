"""Season rows for TV items, built from TMDB season metadata.

TmdbProvider.details() puts a `seasons` list in item metadata; at creation
time it becomes item_seasons rows and is dropped from the metadata blob so
the rows are the single source of truth. Season posters are downloaded
once (fetch-once) into media/seasons/{item_id}/.
"""

from datetime import date
from pathlib import Path

from app.config import get_settings
from app.core.covers import download_image
from app.models import Item, ItemSeason

SEASON_POSTER_URL = "https://image.tmdb.org/t/p/w300{path}"


def create_seasons_from_metadata(db, item: Item) -> None:
    """Turn metadata.seasons into item_seasons rows; rides the caller's txn."""
    if item.type != "tv":
        return
    entries = item.meta.get("seasons")
    if not isinstance(entries, list):
        return

    poster_dir = Path(get_settings().media_dir) / "seasons" / str(item.id)
    for entry in entries:
        number = entry.get("season_number")
        if not isinstance(number, int) or number < 0:
            continue
        poster = entry.get("poster_path")
        db.add(
            ItemSeason(
                item_id=item.id,
                season_number=number,
                tmdb_season_id=entry.get("tmdb_season_id"),
                name=entry.get("name"),
                episode_count=entry.get("episode_count"),
                air_date=_parse_date(entry.get("air_date")),
                poster_path=(
                    download_image(
                        SEASON_POSTER_URL.format(path=poster), poster_dir, f"s{number}"
                    )
                    if poster
                    else None
                ),
            )
        )
    item.meta = {k: v for k, v in item.meta.items() if k != "seasons"}


def _parse_date(raw) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None
