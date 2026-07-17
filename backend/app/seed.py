"""Seed demo data: two users and a varied shelf.

Run inside the backend container:
    docker compose exec backend python -m app.seed

Idempotent: does nothing if the demo user already exists. Cover downloads
are best-effort — offline seeding still works, covers just stay generated.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

import app.models  # noqa: F401
from app.core.covers import download_cover
from app.core.events import record_event
from app.core.security import hash_password
from app.db import SessionLocal
from app.domain.enums import EventType
from app.models import Item, User

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"

OL_COVER = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"


def days_ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


# (type, title, status, format, metadata, extras)
ITEMS: list[tuple] = [
    ("book", "Dune", "in_progress", "physical",
     {"authors": ["Frank Herbert"], "isbn": "9780441172719", "page_count": 412,
      "publisher": "Chilton Books", "year": 1965},
     {"progress_current": 265, "progress_total": 412, "rating": "4.5",
      "review": "Denser than I remembered, but the Fremen chapters absolutely earn it.",
      "purchase_price": "14.99", "currency": "EUR", "days": 120,
      "borrowed_by": "Sanne", "loaned_days": 30}),
    ("book", "Project Hail Mary", "completed", "physical",
     {"authors": ["Andy Weir"], "isbn": "9780593135204", "page_count": 476, "year": 2021},
     {"rating": "5.0", "review": "Rocky is the best character in years. Amaze.",
      "purchase_price": "22.50", "currency": "EUR", "days": 200, "completed_days": 150}),
    ("book", "The Name of the Wind", "backlog", "physical",
     {"authors": ["Patrick Rothfuss"], "isbn": "9780756404741", "page_count": 662, "year": 2007},
     {"purchase_price": "12.00", "currency": "EUR", "days": 45}),
    ("book", "Thinking, Fast and Slow", "completed", "digital",
     {"authors": ["Daniel Kahneman"], "isbn": "9780374533557", "page_count": 499, "year": 2011},
     {"rating": "4.0", "days": 260, "completed_days": 190}),
    ("book", "The Wind-Up Bird Chronicle", "wishlist", None,
     {"authors": ["Haruki Murakami"], "isbn": "9780679775430", "year": 1994},
     {"days": 90}),
    ("movie", "Blade Runner 2049", "completed", "physical",
     {"director": "Denis Villeneuve", "year": 2017, "runtime": 164, "tmdb_id": 335984},
     {"rating": "5.0", "review": "Every frame a painting. The 4K disc is stunning.",
      "purchase_price": "19.99", "currency": "EUR", "days": 300, "completed_days": 290}),
    ("movie", "Spirited Away", "backlog", "physical",
     {"director": "Hayao Miyazaki", "year": 2001, "runtime": 125, "tmdb_id": 129},
     {"purchase_price": "24.99", "currency": "EUR", "days": 20}),
    ("movie", "The Grand Budapest Hotel", "completed", "physical",
     {"director": "Wes Anderson", "year": 2014, "runtime": 99, "tmdb_id": 120467},
     {"rating": "4.5", "days": 240, "completed_days": 230, "purchase_price": "9.99",
      "currency": "EUR"}),
    ("movie", "Mad Max: Fury Road", "backlog", "digital",
     {"director": "George Miller", "year": 2015, "runtime": 120, "tmdb_id": 76341},
     {"days": 15}),
    ("movie", "Oppenheimer", "wishlist", None,
     {"director": "Christopher Nolan", "year": 2023, "runtime": 180, "tmdb_id": 872585},
     {"days": 60}),
    ("game", "Hollow Knight", "in_progress", "digital",
     {"platform": "Switch", "developer": "Team Cherry", "year": 2017, "igdb_id": 26195},
     {"progress_current": 31, "progress_total": 60, "rating": "4.5",
      "purchase_price": "14.99", "currency": "EUR", "days": 80}),
    ("game", "Elden Ring", "in_progress", "physical",
     {"platform": "PS5", "developer": "FromSoftware", "year": 2022, "igdb_id": 119133},
     {"progress_current": 74, "progress_total": 120, "purchase_price": "59.99",
      "currency": "EUR", "days": 140}),
    ("game", "Stardew Valley", "completed", "digital",
     {"platform": "PC", "developer": "ConcernedApe", "year": 2016, "igdb_id": 17000},
     {"rating": "5.0", "review": "500 hours in, still relaxing.", "days": 400,
      "completed_days": 100, "purchase_price": "13.99", "currency": "EUR"}),
    ("game", "Outer Wilds", "completed", "digital",
     {"platform": "PC", "developer": "Mobius Digital", "year": 2019, "igdb_id": 11737},
     {"rating": "5.0", "review": "The one game I wish I could forget and replay.",
      "days": 320, "completed_days": 280}),
    ("game", "Hollow Knight: Silksong", "wishlist", None,
     {"platform": "Switch", "developer": "Team Cherry", "igdb_id": 92317},
     {"days": 500}),
    ("game", "Celeste", "abandoned", "digital",
     {"platform": "PC", "developer": "Matt Makes Games", "year": 2018, "igdb_id": 26226},
     {"progress_current": 4, "progress_total": 20, "days": 380,
      "review": "Brilliant, but my thumbs gave up on chapter 7."}),
]


def seed() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == DEMO_EMAIL)):
            print(f"Demo user {DEMO_EMAIL} already exists — nothing to do.")
            return

        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            display_name="Demo",
        )
        db.add(user)
        db.flush()

        for item_type, title, status, fmt, meta, extra in ITEMS:
            created = days_ago(extra.get("days", 30))
            item = Item(
                user_id=user.id,
                type=item_type,
                format=fmt,
                status=status,
                title=title,
                meta=meta,
                progress_current=extra.get("progress_current"),
                progress_total=extra.get("progress_total"),
                rating=Decimal(extra["rating"]) if "rating" in extra else None,
                review=extra.get("review"),
                purchase_price=Decimal(extra["purchase_price"]) if "purchase_price" in extra else None,
                currency=extra.get("currency"),
                acquisition_date=created.date() if status != "wishlist" else None,
                created_at=created,
            )
            if "completed_days" in extra:
                item.completed_at = days_ago(extra["completed_days"])
            if "borrowed_by" in extra:
                item.borrowed_by = extra["borrowed_by"]
                item.loaned_date = days_ago(extra.get("loaned_days", 14)).date()
            db.add(item)
            db.flush()

            record_event(db, item_id=item.id, user_id=user.id,
                         event_type=EventType.ITEM_ADDED,
                         new_value={"status": status, "type": item_type, "title": title})
            if item.completed_at:
                record_event(db, item_id=item.id, user_id=user.id,
                             event_type=EventType.STATUS_CHANGE,
                             old_value={"status": "in_progress"},
                             new_value={"status": "completed"})
            if item.borrowed_by:
                record_event(db, item_id=item.id, user_id=user.id,
                             event_type=EventType.LOAN_OUT,
                             new_value={"borrowed_by": item.borrowed_by,
                                        "loaned_date": str(item.loaned_date)})

            # Best-effort real covers for books (works offline: just skipped).
            isbn = meta.get("isbn")
            if isbn:
                item.cover_path = download_cover(OL_COVER.format(isbn=isbn), item.id)

        db.commit()
        print(f"Seeded {len(ITEMS)} items for {DEMO_EMAIL} (password: {DEMO_PASSWORD})")


if __name__ == "__main__":
    seed()
