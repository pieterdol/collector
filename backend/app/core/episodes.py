"""Episode rows for a tracked TV season, fetched lazily from TMDB.

TMDB needs one call per season for the episode list, so it happens the
first time a season is opened rather than at add time — a show nobody
expands costs nothing. Rows are upserted by episode number, so a re-sync
of a running show adds what is new and never loses watch state.

Season and episode watch flags stay consistent in both directions:
`sync_season_watched` derives the season from its episodes, and
`set_all_episodes_watched` is the bulk "mark the whole season" path.
"""

from app.core.seasons import parse_date
from app.domain.enums import ItemType
from app.models import Item, ItemEpisode, ItemSeason
from app.providers import get_provider

FIELDS = ("tmdb_episode_id", "name", "overview", "runtime")


def fetch_season_episodes(db, item: Item, season: ItemSeason, force: bool = False) -> bool:
    """Sync one season's episodes from TMDB. False when the show has no match.

    Rides the caller's transaction; only the provider cache commits itself.
    """
    tmdb_id = item.meta.get("tmdb_id")
    if not tmdb_id:
        return False
    entries = get_provider(ItemType.TV, db).season_episodes(
        str(tmdb_id), season.season_number, force=force
    )
    if not entries:
        return False

    existing = {e.episode_number: e for e in season.episodes}
    for entry in entries:
        number = entry["episode_number"]
        row = existing.get(number)
        if row is None:
            row = ItemEpisode(season_id=season.id, episode_number=number)
            season.episodes.append(row)
        for field in FIELDS:
            setattr(row, field, entry[field])
        row.air_date = parse_date(entry["air_date"])
    # TMDB is the authority on how many episodes a season has.
    season.episode_count = len(season.episodes)
    return True


def set_all_episodes_watched(season: ItemSeason, watched: bool) -> None:
    """Bulk mark from the season control; logged as one season event."""
    for episode in season.episodes:
        episode.watched = watched


def sync_season_watched(season: ItemSeason) -> bool:
    """Derive season.watched from its episodes; True when the flag flipped.

    Seasons without episode rows keep their manually set flag.
    """
    if not season.episodes:
        return False
    watched = all(e.watched for e in season.episodes)
    if season.watched == watched:
        return False
    season.watched = watched
    return True
