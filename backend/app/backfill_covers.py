"""Backfill covers for games that have none, via IGDB's Steam-appid mapping.

Run inside the backend container:
    docker compose exec backend python -m app.backfill_covers

Safe to re-run: only touches games whose cover_path is NULL.
"""

from sqlalchemy import select, text

import app.models  # noqa: F401
from app.core.covers import download_cover
from app.db import SessionLocal
from app.models import Item
from app.providers.igdb import covers_for_steam_appids


def backfill() -> None:
    with SessionLocal() as db:
        items = db.scalars(
            select(Item).where(
                Item.type == "game",
                Item.cover_path.is_(None),
                text("metadata ? 'steam_appid'"),
            )
        ).all()
        if not items:
            print("Every game already has a cover — nothing to do.")
            return
        print(f"{len(items)} games without covers; asking IGDB…")

        covers = covers_for_steam_appids(db, [int(i.meta["steam_appid"]) for i in items])
        print(f"IGDB knows covers for {len(covers)} of them.")

        downloaded = failed = 0
        for item in items:
            url = covers.get(int(item.meta["steam_appid"]))
            if not url:
                continue
            path = download_cover(url, item.id)
            if path:
                item.cover_path = path
                item.meta = {**item.meta, "cover_source_url": url}
                db.commit()
                downloaded += 1
            else:
                failed += 1

        unmatched = len(items) - len(covers)
        print(f"Done: {downloaded} covers added, {failed} downloads failed, "
              f"{unmatched} games IGDB has no cover for (fix those via 'Add cover').")


if __name__ == "__main__":
    backfill()
