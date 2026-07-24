"""Epic import: upload a Heroic store cache or `legendary list --json`
dump; games become digital items, DLC and foreign runners are skipped."""

import json

import httpx
import respx

from app.tests.helpers import auth_headers

# `legendary list --json` — a bare array of games with launcher metadata.
LEGENDARY_DUMP = [
    {
        "app_name": "Bree",
        "app_title": "Alba - A Wildlife Adventure",
        "metadata": {
            "title": "Alba - A Wildlife Adventure",
            "developer": "ustwo games",
            "keyImages": [
                {"type": "DieselGameBox", "url": "https://cdn.epic.test/alba-wide.jpg"},
                {"type": "DieselGameBoxTall", "url": "https://cdn.epic.test/alba-tall.jpg"},
            ],
        },
    },
    {
        "app_name": "Kestrel",
        "app_title": "Celeste",
        "metadata": {"title": "Celeste", "developer": "Matt Makes Games"},
    },
    {
        # DLC: legendary marks these via metadata.mainGameItem.
        "app_name": "BreeDLC",
        "app_title": "Alba Soundtrack",
        "metadata": {"title": "Alba Soundtrack", "mainGameItem": {"id": "abc"}},
    },
]

# Heroic's store_cache/legendary_library.json — {"library": [...]}.
HEROIC_CACHE = {
    "library": [
        {
            "app_name": "Bree",
            "title": "Alba - A Wildlife Adventure",
            "developer": "ustwo games",
            "art_square": "https://cdn.epic.test/alba-square.jpg",
            "runner": "legendary",
        },
        {
            "app_name": "gog-game",
            "title": "Not from Epic",
            "runner": "gog",
        },
    ]
}


def upload(client, headers, payload) -> httpx.Response:
    return client.post(
        "/api/epic/import",
        files={"file": ("library.json", json.dumps(payload), "application/json")},
        headers=headers,
    )


def stub_cdn():
    respx.get(url__regex=r"https://cdn\.epic\.test/.*").mock(
        return_value=httpx.Response(404)
    )


@respx.mock
def test_import_creates_digital_games_and_skips_dlc(client):
    stub_cdn()
    headers = auth_headers(client)
    res = upload(client, headers, LEGENDARY_DUMP)
    assert res.status_code == 200, res.text
    assert res.json() == {"imported": 2, "skipped": 1, "total": 3}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    by_title = {i["title"]: i for i in items}
    assert sorted(by_title) == ["Alba - A Wildlife Adventure", "Celeste"]
    alba = by_title["Alba - A Wildlife Adventure"]
    assert alba["format"] == "digital"
    assert alba["status"] == "backlog"
    assert alba["metadata"]["epic_app_name"] == "Bree"
    assert alba["metadata"]["storefront"] == "Epic Games Store"
    assert alba["metadata"]["developer"] == "ustwo games"
    # Tall box art preferred over the wide one.
    assert alba["metadata"]["cover_source_url"] == "https://cdn.epic.test/alba-tall.jpg"
    assert alba["platform"] == "PC (Microsoft Windows)"


@respx.mock
def test_import_accepts_heroic_cache_and_skips_other_runners(client):
    stub_cdn()
    headers = auth_headers(client)
    res = upload(client, headers, HEROIC_CACHE)
    assert res.status_code == 200, res.text
    assert res.json() == {"imported": 1, "skipped": 1, "total": 2}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert [i["title"] for i in items] == ["Alba - A Wildlife Adventure"]
    assert items[0]["metadata"]["cover_source_url"] == "https://cdn.epic.test/alba-square.jpg"


@respx.mock
def test_reimport_skips_already_imported_games(client):
    stub_cdn()
    headers = auth_headers(client)
    assert upload(client, headers, LEGENDARY_DUMP).json()["imported"] == 2

    res = upload(client, headers, LEGENDARY_DUMP)
    assert res.json() == {"imported": 0, "skipped": 3, "total": 3}


def test_import_rejects_invalid_files(client):
    headers = auth_headers(client)
    res = client.post(
        "/api/epic/import",
        files={"file": ("library.json", b"not json {", "application/json")},
        headers=headers,
    )
    assert res.status_code == 400

    res = upload(client, headers, {"unexpected": "shape"})
    assert res.status_code == 400
    assert "Heroic" in res.json()["detail"] or "legendary" in res.json()["detail"]


def test_import_requires_auth(client):
    assert client.post("/api/epic/import").status_code == 401


@respx.mock
def test_import_records_activity_events(client):
    stub_cdn()
    headers = auth_headers(client)
    upload(client, headers, HEROIC_CACHE)

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    events = client.get(f"/api/items/{items[0]['id']}/activity", headers=headers).json()[
        "events"
    ]
    assert [e["event_type"] for e in events] == ["item_added"]
    assert events[0]["new_value"]["source"] == "epic_import"
