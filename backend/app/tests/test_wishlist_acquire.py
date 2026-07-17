from sqlalchemy import select

from app.db import SessionLocal
from app.models import ActivityEvent
from app.tests.helpers import auth_headers, create_item


def test_wishlist_item_needs_no_format_or_price(client):
    headers = auth_headers(client)
    item = create_item(
        client, headers, status="wishlist", format=None, title="Silksong", type="game"
    )
    assert item["format"] is None
    assert item["purchase_price"] is None


def test_acquire_moves_wishlist_item_to_backlog(client):
    headers = auth_headers(client)
    item = create_item(client, headers, status="wishlist", format=None, title="Silksong")
    res = client.post(
        f"/api/items/{item['id']}/acquire",
        json={
            "format": "digital",
            "purchase_price": 19.99,
            "currency": "EUR",
            "acquisition_date": "2026-07-17",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "backlog"
    assert body["format"] == "digital"
    assert body["purchase_price"] == "19.99"
    assert body["acquisition_date"] == "2026-07-17"

    with SessionLocal() as db:
        evs = db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.item_id == item["id"])
            .order_by(ActivityEvent.created_at)
        ).all()
    assert [e.event_type for e in evs] == ["item_added", "acquired"]
    assert evs[-1].old_value == {"status": "wishlist"}
    assert evs[-1].new_value["status"] == "backlog"


def test_acquire_rejects_non_wishlist_items(client):
    headers = auth_headers(client)
    item = create_item(client, headers, status="backlog")
    res = client.post(
        f"/api/items/{item['id']}/acquire", json={"format": "physical"}, headers=headers
    )
    assert res.status_code == 400


def test_acquiring_a_game_sets_its_platform(client):
    headers = auth_headers(client)
    item = create_item(client, headers, status="wishlist", format=None,
                       title="Silksong", type="game")
    res = client.post(
        f"/api/items/{item['id']}/acquire",
        json={"format": "digital", "platform": "Nintendo Switch"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["platform"] == "Nintendo Switch"
