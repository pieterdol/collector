"""Epic import: upload a Heroic store cache or `legendary list --json`
dump; games become digital items, DLC and foreign runners are skipped.

Like PSN, the upload creates a job that pauses for review; under
TestClient background tasks finish before the response returns, so the
first status poll already shows the review."""

import json

import httpx
import respx

from app.tests.helpers import auth_headers, create_item

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


def start(client, headers, payload) -> httpx.Response:
    return client.post(
        "/api/epic/import",
        files={"file": ("library.json", json.dumps(payload), "application/json")},
        headers=headers,
    )


def review_of(client, headers, payload) -> tuple[str, dict]:
    res = start(client, headers, payload)
    assert res.status_code == 202, res.text
    job_id = res.json()["job_id"]
    status = client.get(f"/api/epic/import/{job_id}", headers=headers)
    assert status.status_code == 200, status.text
    return job_id, status.json()


def confirm(client, headers, job_id, title_ids) -> dict:
    res = client.post(
        f"/api/epic/import/{job_id}/confirm",
        json={"title_ids": title_ids},
        headers=headers,
    )
    assert res.status_code == 202, res.text
    return client.get(f"/api/epic/import/{job_id}", headers=headers).json()


def upload(client, headers, payload) -> dict:
    """Start a job and confirm every candidate; returns the final status."""
    job_id, review = review_of(client, headers, payload)
    if review["status"] != "review":
        return review
    return confirm(client, headers, job_id, [c["title_id"] for c in review["candidates"]])


def counts(job: dict) -> dict:
    return {k: job[k] for k in ("imported", "skipped", "total")}


def stub_cdn():
    respx.get(url__regex=r"https://cdn\.epic\.test/.*").mock(
        return_value=httpx.Response(404)
    )


@respx.mock
def test_import_creates_digital_games_and_skips_dlc(client):
    stub_cdn()
    headers = auth_headers(client)
    job = upload(client, headers, LEGENDARY_DUMP)
    assert counts(job) == {"imported": 2, "skipped": 0, "total": 2}

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
def test_dlc_never_reaches_the_review(client):
    """DLC isn't reviewable junk — it's not a library item at all."""
    stub_cdn()
    headers = auth_headers(client)
    _, review = review_of(client, headers, LEGENDARY_DUMP)
    names = {c["name"] for c in review["candidates"]} | {e["name"] for e in review["excluded"]}
    assert "Alba Soundtrack" not in names


@respx.mock
def test_import_accepts_heroic_cache_and_skips_other_runners(client):
    stub_cdn()
    headers = auth_headers(client)
    job = upload(client, headers, HEROIC_CACHE)
    assert counts(job) == {"imported": 1, "skipped": 0, "total": 1}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert [i["title"] for i in items] == ["Alba - A Wildlife Adventure"]
    assert items[0]["metadata"]["cover_source_url"] == "https://cdn.epic.test/alba-square.jpg"


@respx.mock
def test_non_games_are_auto_excluded_but_rescuable(client):
    stub_cdn()
    headers = auth_headers(client)
    payload = LEGENDARY_DUMP + [
        {"app_name": "Junk1", "app_title": "Alba Demo", "metadata": {"title": "Alba Demo"}},
        {"app_name": "Junk2", "app_title": "Prime Video", "metadata": {"title": "Prime Video"}},
        {
            "app_name": "Junk3",
            "app_title": "Galaxy Common Redistributables",
            "metadata": {"title": "Galaxy Common Redistributables"},
        },
    ]
    job_id, review = review_of(client, headers, payload)

    assert {c["name"] for c in review["candidates"]} == {
        "Alba - A Wildlife Adventure",
        "Celeste",
    }
    excluded = {e["name"]: e["reason"] for e in review["excluded"]}
    assert set(excluded) == {"Alba Demo", "Prime Video", "Galaxy Common Redistributables"}
    assert all(excluded.values())

    # Rescue one: it imports alongside the candidates.
    job = confirm(client, headers, job_id, ["Bree", "Junk1"])
    titles = [i["title"] for i in client.get("/api/items?type=game", headers=headers).json()["items"]]
    assert sorted(titles) == ["Alba - A Wildlife Adventure", "Alba Demo"]
    assert job["imported"] == 2


@respx.mock
def test_titles_already_in_the_library_are_flagged(client):
    stub_cdn()
    headers = auth_headers(client)
    create_item(client, headers, type="game", title="Celeste", format="physical")

    _, review = review_of(client, headers, LEGENDARY_DUMP)
    assert [c["name"] for c in review["candidates"]] == ["Alba - A Wildlife Adventure"]
    flagged = next(e for e in review["excluded"] if e["name"] == "Celeste")
    assert flagged["reason"] == "already in your collection"


@respx.mock
def test_reimport_flags_previously_imported_games(client):
    stub_cdn()
    headers = auth_headers(client)
    assert upload(client, headers, LEGENDARY_DUMP)["imported"] == 2

    _, review = review_of(client, headers, LEGENDARY_DUMP)
    assert review["candidates"] == []
    assert {e["reason"] for e in review["excluded"]} == {"already in your collection"}


def test_import_rejects_invalid_files(client):
    headers = auth_headers(client)
    res = client.post(
        "/api/epic/import",
        files={"file": ("library.json", b"not json {", "application/json")},
        headers=headers,
    )
    assert res.status_code == 400

    res = start(client, headers, {"unexpected": "shape"})
    assert res.status_code == 400
    assert "Heroic" in res.json()["detail"] or "legendary" in res.json()["detail"]


def test_import_requires_auth(client):
    assert client.post("/api/epic/import").status_code == 401
    assert client.get("/api/epic/import/whatever").status_code == 401


@respx.mock
def test_jobs_are_scoped_to_their_owner(client):
    stub_cdn()
    mine = auth_headers(client, email="epic-owner@example.com")
    theirs = auth_headers(client, email="epic-snoop@example.com")
    job_id = start(client, mine, LEGENDARY_DUMP).json()["job_id"]

    assert client.get(f"/api/epic/import/{job_id}", headers=theirs).status_code == 404
    assert client.post(
        f"/api/epic/import/{job_id}/confirm", json={"title_ids": []}, headers=theirs
    ).status_code == 404


@respx.mock
def test_confirm_requires_a_job_in_review(client):
    stub_cdn()
    headers = auth_headers(client)
    job_id, review = review_of(client, headers, LEGENDARY_DUMP)
    confirm(client, headers, job_id, [c["title_id"] for c in review["candidates"]])

    res = client.post(
        f"/api/epic/import/{job_id}/confirm", json={"title_ids": []}, headers=headers
    )
    assert res.status_code == 409


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
