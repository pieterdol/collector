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


def start(client, headers, payload) -> httpx.Response:
    return client.post(
        "/api/gog/import",
        files={"file": ("gog_library.json", json.dumps(payload), "application/json")},
        headers=headers,
    )


def review_of(client, headers, payload) -> tuple[str, dict]:
    res = start(client, headers, payload)
    assert res.status_code == 202, res.text
    job_id = res.json()["job_id"]
    return job_id, client.get(f"/api/gog/import/{job_id}", headers=headers).json()


def confirm(client, headers, job_id, title_ids) -> dict:
    res = client.post(
        f"/api/gog/import/{job_id}/confirm",
        json={"title_ids": title_ids},
        headers=headers,
    )
    assert res.status_code == 202, res.text
    return client.get(f"/api/gog/import/{job_id}", headers=headers).json()


def upload(client, headers, payload) -> dict:
    job_id, review = review_of(client, headers, payload)
    return confirm(client, headers, job_id, [c["title_id"] for c in review["candidates"]])


def counts(job: dict) -> dict:
    return {k: job[k] for k in ("imported", "skipped", "total")}


def stub_cdn():
    respx.get(url__regex=r"https://cdn\.gog\.test/.*").mock(return_value=httpx.Response(404))


@respx.mock
def test_import_creates_gog_games_skipping_dlc_and_other_runners(client):
    stub_cdn()
    headers = auth_headers(client)
    job = upload(client, headers, GOG_CACHE)
    assert counts(job) == {"imported": 1, "skipped": 0, "total": 1}

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
    assert upload(client, headers, GOG_CACHE_LEGACY)["imported"] == 1


@respx.mock
def test_redistributables_are_auto_excluded(client):
    """Heroic's GOG cache carries a "Galaxy Common Redistributables" row."""
    stub_cdn()
    headers = auth_headers(client)
    payload = {
        "games": GOG_CACHE["library"]
        + [
            {
                "app_name": "gog-redist",
                "title": "Galaxy Common Redistributables",
                "runner": "gog",
            }
        ]
    }
    _, review = review_of(client, headers, payload)
    assert [c["name"] for c in review["candidates"]] == ["The Witcher 3: Wild Hunt"]
    flagged = next(e for e in review["excluded"] if e["name"] == "Galaxy Common Redistributables")
    assert flagged["reason"]


@respx.mock
def test_reimport_flags_previously_imported_games(client):
    stub_cdn()
    headers = auth_headers(client)
    assert upload(client, headers, GOG_CACHE)["imported"] == 1

    _, review = review_of(client, headers, GOG_CACHE)
    assert review["candidates"] == []
    assert {e["reason"] for e in review["excluded"]} == {"already in your collection"}


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
    epic_res = client.post(
        "/api/epic/import",
        files={"file": ("library.json", json.dumps(epic_payload), "application/json")},
        headers=headers,
    )
    epic_job = epic_res.json()["job_id"]
    client.post(
        f"/api/epic/import/{epic_job}/confirm",
        json={"title_ids": ["1207658924"]},
        headers=headers,
    )

    assert upload(client, headers, GOG_CACHE)["imported"] == 1
    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert sorted(i["title"] for i in items) == ["Epic Twin", "The Witcher 3: Wild Hunt"]
