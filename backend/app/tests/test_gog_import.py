"""GOG import: upload Heroic's gog_library.json; GOG-runner games become
digital items, Epic entries and DLC are skipped."""

import json

import httpx
import respx

from app.tests.helpers import auth_headers

# Heroic store_cache/gog_library.json — same envelope as the legendary one.
GOG_CACHE = {
    "library": [
        {
            "app_name": "1207658924",
            "title": "The Witcher 3: Wild Hunt",
            "developer": "CD PROJEKT RED",
            "art_square": "https://cdn.gog.test/witcher3.jpg",
            "runner": "gog",
        },
        {
            "app_name": "1207658925",
            "title": "Witcher 3 Expansion",
            "runner": "gog",
            "install": {"is_dlc": True},
        },
        {
            "app_name": "Bree",
            "title": "Not a GOG game",
            "runner": "legendary",
        },
    ]
}

# Older Heroic versions wrapped the list as {"games": [...]}.
GOG_CACHE_LEGACY = {
    "games": [
        {
            "app_name": "1207658930",
            "title": "Cyberpunk 2077",
            "runner": "gog",
        }
    ]
}


def upload(client, headers, payload) -> httpx.Response:
    return client.post(
        "/api/gog/import",
        files={"file": ("gog_library.json", json.dumps(payload), "application/json")},
        headers=headers,
    )


def stub_cdn():
    respx.get(url__regex=r"https://cdn\.gog\.test/.*").mock(return_value=httpx.Response(404))


@respx.mock
def test_import_creates_gog_games_skipping_dlc_and_other_runners(client):
    stub_cdn()
    headers = auth_headers(client)
    res = upload(client, headers, GOG_CACHE)
    assert res.status_code == 200, res.text
    assert res.json() == {"imported": 1, "skipped": 2, "total": 3}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert [i["title"] for i in items] == ["The Witcher 3: Wild Hunt"]
    witcher = items[0]
    assert witcher["format"] == "digital"
    assert witcher["status"] == "backlog"
    assert witcher["metadata"]["gog_product_id"] == "1207658924"
    assert witcher["metadata"]["storefront"] == "GOG"
    assert witcher["metadata"]["developer"] == "CD PROJEKT RED"
    assert witcher["metadata"]["cover_source_url"] == "https://cdn.gog.test/witcher3.jpg"
    assert witcher["platform"] == "PC (Microsoft Windows)"


@respx.mock
def test_import_accepts_older_games_envelope(client):
    stub_cdn()
    headers = auth_headers(client)
    res = upload(client, headers, GOG_CACHE_LEGACY)
    assert res.json() == {"imported": 1, "skipped": 0, "total": 1}


@respx.mock
def test_reimport_skips_already_imported_games(client):
    stub_cdn()
    headers = auth_headers(client)
    assert upload(client, headers, GOG_CACHE).json()["imported"] == 1

    res = upload(client, headers, GOG_CACHE)
    assert res.json() == {"imported": 0, "skipped": 3, "total": 3}


def test_import_requires_auth(client):
    assert client.post("/api/gog/import").status_code == 401


@respx.mock
def test_gog_and_epic_imports_do_not_collide(client):
    """The same app_name under different stores must not dedupe across them."""
    stub_cdn()
    respx.get(url__regex=r"https://cdn\.epic\.test/.*").mock(
        return_value=httpx.Response(404)
    )
    headers = auth_headers(client)
    epic_payload = {
        "library": [{"app_name": "1207658924", "title": "Epic Twin", "runner": "legendary"}]
    }
    client.post(
        "/api/epic/import",
        files={"file": ("library.json", json.dumps(epic_payload), "application/json")},
        headers=headers,
    )
    res = upload(client, headers, GOG_CACHE)
    assert res.json()["imported"] == 1

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert sorted(i["title"] for i in items) == ["Epic Twin", "The Witcher 3: Wild Hunt"]
