"""Backfill release dates for games (via IGDB, batched) and movies (TMDB).

Run inside the backend container:
    docker compose exec backend python -m app.backfill_release_dates

Idempotent: only touches items without metadata.release_date. Movies also
pick up director/runtime when missing (same TMDB response).
"""

from sqlalchemy import select, text

import app.models  # noqa: F401
from app.db import SessionLocal
from app.models import Item
from app.providers.igdb import release_dates_for_igdb_ids, release_dates_for_steam_appids
from app.providers.tmdb import TmdbProvider


def _set_date(db, item: Item, date: str) -> None:
    item.meta = {**item.meta, "release_date": date, "year": int(date[:4])}
    db.commit()


def backfill() -> None:
    with SessionLocal() as db:
        games = db.scalars(
            select(Item).where(
                Item.type == "game", text("NOT metadata ? 'release_date'")
            )
        ).all()
        by_steam = [i for i in games if i.meta.get("steam_appid")]
        by_igdb = [i for i in games if not i.meta.get("steam_appid") and i.meta.get("igdb_id")]
        print(f"Games without a release date: {len(games)} "
              f"({len(by_steam)} via Steam id, {len(by_igdb)} via IGDB id)")

        steam_dates = release_dates_for_steam_appids(
            db, [int(i.meta["steam_appid"]) for i in by_steam]
        )
        igdb_dates = release_dates_for_igdb_ids(db, [int(i.meta["igdb_id"]) for i in by_igdb])

        games_done = 0
        for item in by_steam:
            date = steam_dates.get(int(item.meta["steam_appid"]))
            if date:
                _set_date(db, item, date)
                games_done += 1
        for item in by_igdb:
            date = igdb_dates.get(int(item.meta["igdb_id"]))
            if date:
                _set_date(db, item, date)
                games_done += 1
        print(f"Games updated: {games_done}, unmatched: {len(games) - games_done}")

        movies = db.scalars(
            select(Item).where(
                Item.type == "movie",
                text("NOT metadata ? 'release_date'"),
                text("metadata ? 'tmdb_id'"),
            )
        ).all()
        print(f"Movies without a release date: {len(movies)}")
        provider = TmdbProvider(db)
        movies_done = 0
        if provider.available:
            for item in movies:
                result = provider.details(str(item.meta["tmdb_id"]))
                if result is None:
                    continue
                extra = {
                    k: v
                    for k, v in result.metadata.items()
                    if k in ("release_date", "director", "runtime", "year")
                    and v is not None
                    and item.meta.get(k) is None
                }
                if extra:
                    item.meta = {**item.meta, **extra}
                    db.commit()
                    if "release_date" in extra:
                        movies_done += 1
        print(f"Movies updated: {movies_done}")


if __name__ == "__main__":
    backfill()
