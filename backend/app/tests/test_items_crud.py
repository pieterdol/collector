from sqlalchemy import select

from app.db import SessionLocal
from app.models import ActivityEvent
from app.tests.helpers import auth_headers, create_item


def events_for(item_id: str) -> list[ActivityEvent]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(ActivityEvent)
                .where(ActivityEvent.item_id == item_id)
                .order_by(ActivityEvent.created_at)
            )
        )


def test_create_item_returns_full_shape_and_records_event(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    assert item["title"] == "Dune"
    assert item["metadata"] == {"authors": ["Frank Herbert"]}
    assert item["status"] == "backlog"
    assert item["completed_at"] is None
    evs = events_for(item["id"])
    assert [e.event_type for e in evs] == ["item_added"]


def test_items_require_auth(client):
    assert client.get("/api/items").status_code == 401
    assert client.post("/api/items", json={}).status_code == 401


def test_users_only_see_their_own_items(client):
    mine = auth_headers(client, email="me@example.com")
    theirs = auth_headers(client, email="them@example.com")
    create_item(client, mine, title="Mine")
    create_item(client, theirs, title="Theirs")

    titles = [i["title"] for i in client.get("/api/items", headers=mine).json()["items"]]
    assert titles == ["Mine"]

    other_id = client.get("/api/items", headers=theirs).json()["items"][0]["id"]
    assert client.get(f"/api/items/{other_id}", headers=mine).status_code == 404
    assert client.delete(f"/api/items/{other_id}", headers=mine).status_code == 404


def test_patch_updates_fields(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    res = client.patch(
        f"/api/items/{item['id']}",
        json={"review": "Great.", "metadata": {"authors": ["Frank Herbert"], "isbn": "123"}},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["review"] == "Great."
    assert res.json()["metadata"]["isbn"] == "123"


def test_status_change_records_event_and_sets_completed_at(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    res = client.patch(
        f"/api/items/{item['id']}", json={"status": "completed"}, headers=headers
    )
    assert res.json()["completed_at"] is not None
    evs = events_for(item["id"])
    assert [e.event_type for e in evs] == ["item_added", "status_change"]
    assert evs[-1].old_value == {"status": "backlog"}
    assert evs[-1].new_value == {"status": "completed"}


def test_leaving_completed_clears_completed_at(client):
    headers = auth_headers(client)
    item = create_item(client, headers, status="completed")
    assert item["completed_at"] is not None
    res = client.patch(
        f"/api/items/{item['id']}", json={"status": "in_progress"}, headers=headers
    )
    assert res.json()["completed_at"] is None


def test_progress_update_records_event(client):
    headers = auth_headers(client)
    item = create_item(client, headers, progress_total=412)
    client.patch(f"/api/items/{item['id']}", json={"progress_current": 100}, headers=headers)
    evs = events_for(item["id"])
    assert evs[-1].event_type == "progress_update"
    assert evs[-1].new_value["progress_current"] == "100"


def test_unchanged_progress_records_no_event(client):
    headers = auth_headers(client)
    item = create_item(client, headers, progress_current=100, progress_total=412)
    client.patch(f"/api/items/{item['id']}", json={"progress_current": 100}, headers=headers)
    client.patch(
        f"/api/items/{item['id']}",
        json={"progress_current": 100, "progress_total": 412},
        headers=headers,
    )
    evs = events_for(item["id"])
    assert [e.event_type for e in evs] == ["item_added"]


def test_rating_set_records_event(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    res = client.patch(f"/api/items/{item['id']}", json={"rating": 4.5}, headers=headers)
    assert res.status_code == 200
    evs = events_for(item["id"])
    assert evs[-1].event_type == "rating_set"


def test_invalid_rating_rejected_by_validation(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    res = client.patch(f"/api/items/{item['id']}", json={"rating": 4.3}, headers=headers)
    assert res.status_code == 422


def test_loan_out_and_return_record_events(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    client.patch(
        f"/api/items/{item['id']}",
        json={"borrowed_by": "Sanne", "loaned_date": "2026-06-12"},
        headers=headers,
    )
    client.patch(
        f"/api/items/{item['id']}", json={"returned_date": "2026-07-01"}, headers=headers
    )
    evs = events_for(item["id"])
    assert [e.event_type for e in evs] == ["item_added", "loan_out", "loan_return"]


def test_delete_removes_item(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    assert client.delete(f"/api/items/{item['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/items/{item['id']}", headers=headers).status_code == 404


def test_item_activity_endpoint_lists_events(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    client.patch(f"/api/items/{item['id']}", json={"status": "in_progress"}, headers=headers)
    res = client.get(f"/api/items/{item['id']}/activity", headers=headers)
    assert res.status_code == 200
    types = [e["event_type"] for e in res.json()["events"]]
    assert types == ["status_change", "item_added"]  # newest first


def test_delete_single_activity_event(client):
    headers = auth_headers(client)
    item = create_item(client, headers)
    client.patch(f"/api/items/{item['id']}", json={"status": "in_progress"}, headers=headers)
    events = client.get(f"/api/items/{item['id']}/activity", headers=headers).json()["events"]
    assert len(events) == 2
    target = events[0]  # the status_change

    res = client.delete(f"/api/items/{item['id']}/activity/{target['id']}", headers=headers)
    assert res.status_code == 204
    remaining = client.get(f"/api/items/{item['id']}/activity", headers=headers).json()["events"]
    assert [e["id"] for e in remaining] == [events[1]["id"]]


def test_delete_activity_event_checks_ownership(client):
    mine = auth_headers(client, email="mine2@example.com")
    theirs = auth_headers(client, email="theirs2@example.com")
    item = create_item(client, theirs)
    event = client.get(f"/api/items/{item['id']}/activity", headers=theirs).json()["events"][0]
    res = client.delete(f"/api/items/{item['id']}/activity/{event['id']}", headers=mine)
    assert res.status_code == 404


def test_delete_activity_event_must_belong_to_item(client):
    headers = auth_headers(client)
    item_a = create_item(client, headers, title="A")
    item_b = create_item(client, headers, title="B")
    event_a = client.get(f"/api/items/{item_a['id']}/activity", headers=headers).json()["events"][0]
    res = client.delete(f"/api/items/{item_b['id']}/activity/{event_a['id']}", headers=headers)
    assert res.status_code == 404
