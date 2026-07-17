from datetime import UTC, datetime

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Item
from app.tests.helpers import auth_headers, create_item


def seed_stats_data(client, headers):
    create_item(client, headers, type="book", title="Reading Now", status="in_progress",
                progress_current=100, progress_total=400)
    create_item(client, headers, type="book", title="Read This Year", status="completed",
                purchase_price=10, currency="EUR")
    create_item(client, headers, type="movie", title="Owned Disc", format="physical",
                purchase_price=20, currency="EUR", acquisition_date=datetime.now(UTC).date().isoformat())
    create_item(client, headers, type="movie", title="Digital Movie", format="digital")
    create_item(client, headers, type="game", title="Steam Game", format="digital",
                status="in_progress", progress_current=40, progress_total=60,
                metadata={"steam_appid": 1, "platform": "PC (Steam)"})
    create_item(client, headers, type="game", title="Boxed Game", format="physical")
    create_item(client, headers, type="game", title="Wanted Game", status="wishlist", format=None)
    # a loan
    items = client.get("/api/items?q=Owned Disc", headers=headers).json()["items"]
    client.patch(f"/api/items/{items[0]['id']}",
                 json={"borrowed_by": "Sam", "loaned_date": "2026-06-26"}, headers=headers)


def test_stats_requires_auth(client):
    assert client.get("/api/stats").status_code == 401


def test_stats_tiles(client):
    headers = auth_headers(client)
    seed_stats_data(client, headers)
    body = client.get("/api/stats", headers=headers).json()

    book = body["tiles"]["book"]
    assert book["total"] == 2
    assert book["in_progress"] == 1
    assert book["completed_this_year"] == 1

    movie = body["tiles"]["movie"]
    assert movie["total"] == 2
    assert movie["physical"] == 1
    assert movie["digital"] == 1

    game = body["tiles"]["game"]
    assert game["total"] == 3  # wishlist games count toward the shelf number
    assert game["via_steam"] == 1
    assert game["hours_played"] == 40.0

    value = body["tiles"]["value"]
    assert float(value["total"]) == 30.0
    assert value["currency"] == "EUR"
    assert float(value["this_month"]) == 20.0  # only the acquisition dated this month


def test_stats_continue_lists_in_progress_items(client):
    headers = auth_headers(client)
    seed_stats_data(client, headers)
    body = client.get("/api/stats", headers=headers).json()
    titles = [c["title"] for c in body["continue"]]
    assert "Reading Now" in titles and "Steam Game" in titles
    reading = next(c for c in body["continue"] if c["title"] == "Reading Now")
    assert reading["pct"] == 25


def test_stats_loans_and_recent_activity(client):
    headers = auth_headers(client)
    seed_stats_data(client, headers)
    body = client.get("/api/stats", headers=headers).json()

    assert body["loans"][0]["title"] == "Owned Disc"
    assert body["loans"][0]["borrowed_by"] == "Sam"

    types = [e["event_type"] for e in body["recent"]]
    assert "loan_out" in types and "item_added" in types
    assert all("title" in e for e in body["recent"])


def test_stats_only_counts_own_items(client):
    mine = auth_headers(client, email="mine@example.com")
    other = auth_headers(client, email="other@example.com")
    create_item(client, other, type="book", title="Not Mine")
    body = client.get("/api/stats", headers=mine).json()
    assert body["tiles"]["book"]["total"] == 0


def test_stats_completed_last_year_not_counted(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="book", title="Old Read", status="completed")
    with SessionLocal() as db:
        db.execute(
            update(Item)
            .where(Item.id == item["id"])
            .values(completed_at=datetime(2024, 3, 1, tzinfo=UTC))
        )
        db.commit()
    body = client.get("/api/stats", headers=headers).json()
    assert body["tiles"]["book"]["completed_this_year"] == 0
