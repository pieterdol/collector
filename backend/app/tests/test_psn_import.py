"""PSN import: exchange an NPSSO cookie for a token, pull the purchased
list, and keep PS Plus-gated titles out unless explicitly included.

The import runs as a background job (big libraries outlive proxy
timeouts); the API returns a job id that the UI polls for progress.
Under TestClient, background tasks complete before the response returns,
so the first poll already sees the final state."""

import json

import httpx
import respx

from app.providers.psn import AUTH_BASE, GAMELIST_URL, GRAPHQL_URL
from app.tests.helpers import auth_headers, create_item

REDIRECT = "com.scee.psxandroid.scecompcall://redirect?code=v3.AbCdEf"

# Real entries carry a "_00" service suffix on titleId and a per-title
# subscriptionService tag ("NONE" for purchases, "PS_PLUS" for claims).
PURCHASED = [
    {
        "name": "Returnal",
        "titleId": "PPSA01284_00",
        "platform": "PS5",
        "subscriptionService": "NONE",
        "image": {"url": "https://cdn.psn.test/returnal.png"},
    },
    {
        "name": "Bloodborne",
        "titleId": "CUSA00207_00",
        "platform": "PS4",
        "subscriptionService": "NONE",
        "image": {"url": "https://cdn.psn.test/bloodborne.png"},
    },
]

PS_PLUS = [
    {
        "name": "Stray",
        "titleId": "PPSA04640_00",
        "platform": "PS5",
        "subscriptionService": "PS_PLUS",
        "image": {"url": "https://cdn.psn.test/stray.png"},
    },
]


def mock_psn(purchased=None, ps_plus=None, code_ok=True, played=None):
    respx.get(f"{AUTH_BASE}/authz/v3/oauth/authorize").mock(
        return_value=httpx.Response(
            302,
            headers={
                "Location": REDIRECT if code_ok
                else "com.scee.psxandroid.scecompcall://redirect?error=invalid"
            },
        )
    )
    respx.post(f"{AUTH_BASE}/authz/v3/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123"})
    )
    respx.get(url__regex=r"https://cdn\.psn\.test/.*").mock(
        return_value=httpx.Response(404)
    )
    respx.get(GAMELIST_URL).mock(
        return_value=httpx.Response(
            200, json={"titles": played or [], "totalItemCount": len(played or [])}
        )
    )

    def graphql(request):
        # Sony semantics (verified live): "NONE" means UNFILTERED — the
        # response mixes purchases and PS Plus claims; per-title
        # subscriptionService is the only reliable distinction.
        variables = json.loads(request.content)["variables"]
        games = (purchased or []) + (ps_plus or [])
        if variables["subscriptionService"] == "PS_PLUS":
            games = ps_plus or []
        start = variables["start"]
        page = games[start : start + variables["size"]]
        return httpx.Response(
            200,
            json={
                "data": {
                    "purchasedTitlesRetrieve": {
                        "games": page,
                        "pageInfo": {"totalCount": len(games)},
                    }
                }
            },
        )

    respx.post(GRAPHQL_URL).mock(side_effect=graphql)


def start_job(client, headers, **body) -> str:
    res = client.post(
        "/api/psn/import", json={"npsso": "npsso-cookie-value", **body}, headers=headers
    )
    assert res.status_code == 202, res.text
    return res.json()["job_id"]


def job_status(client, headers, job_id) -> dict:
    res = client.get(f"/api/psn/import/{job_id}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def confirm(client, headers, job_id, title_ids) -> dict:
    res = client.post(
        f"/api/psn/import/{job_id}/confirm", json={"title_ids": title_ids}, headers=headers
    )
    assert res.status_code == 202, res.text
    return job_status(client, headers, job_id)


def do_import(client, headers, **body) -> dict:
    """Start a job, confirm every candidate, return the final status."""
    job_id = start_job(client, headers, **body)
    job = job_status(client, headers, job_id)
    if job["status"] != "review":
        return job
    return confirm(client, headers, job_id, [c["title_id"] for c in job["candidates"]])


def counts(job: dict) -> dict:
    return {k: job[k] for k in ("imported", "skipped", "total")}


@respx.mock
def test_import_excludes_ps_plus_by_default(client):
    mock_psn(purchased=PURCHASED, ps_plus=PS_PLUS)
    headers = auth_headers(client)
    job = do_import(client, headers)
    assert job["status"] == "done"
    assert counts(job) == {"imported": 2, "skipped": 0, "total": 2}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    by_title = {i["title"]: i for i in items}
    assert sorted(by_title) == ["Bloodborne", "Returnal"]
    returnal = by_title["Returnal"]
    assert returnal["format"] == "digital"
    assert returnal["status"] == "backlog"
    assert returnal["metadata"]["psn_title_id"] == "PPSA01284"
    assert returnal["metadata"]["storefront"] == "PlayStation Store"
    assert returnal["metadata"]["cover_source_url"] == "https://cdn.psn.test/returnal.png"
    assert returnal["platform"] == "PlayStation 5"
    assert by_title["Bloodborne"]["platform"] == "PlayStation 4"
    assert "subscription" not in returnal["metadata"]


@respx.mock
def test_include_ps_plus_imports_and_marks_them(client):
    mock_psn(purchased=PURCHASED, ps_plus=PS_PLUS)
    headers = auth_headers(client)
    job = do_import(client, headers, include_ps_plus=True)
    assert counts(job) == {"imported": 3, "skipped": 0, "total": 3}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    stray = next(i for i in items if i["title"] == "Stray")
    assert stray["metadata"]["subscription"] == "PS Plus"


@respx.mock
def test_dedupe_option_keeps_only_the_ps5_version(client):
    cross_gen = PURCHASED + [
        {
            # Same game as the PS5 "Returnal" entry, modulo the ™ mark.
            "name": "Returnal™",
            "titleId": "CUSA11111_00",
            "platform": "PS4",
            "subscriptionService": "NONE",
            "image": {"url": "https://cdn.psn.test/returnal-ps4.png"},
        },
    ]
    mock_psn(purchased=cross_gen)
    headers = auth_headers(client)

    # Off by default: both versions import.
    job = do_import(client, headers)
    assert job["imported"] == 3

    # On: the PS4 twin moves to the auto-excluded review list.
    other = auth_headers(client, email="dedupe@example.com")
    job_id = start_job(client, other, dedupe_cross_gen=True)
    review = job_status(client, other, job_id)
    twin = next(e for e in review["excluded"] if e["title_id"] == "CUSA11111")
    assert "PS5" in twin["reason"]

    job = confirm(client, other, job_id, [c["title_id"] for c in review["candidates"]])
    assert counts(job) == {"imported": 2, "skipped": 0, "total": 2}
    items = client.get("/api/items?type=game", headers=other).json()["items"]
    platforms = {i["title"]: i["platform"] for i in items}
    assert platforms == {"Returnal": "PlayStation 5", "Bloodborne": "PlayStation 4"}


JUNK = [
    {
        "name": "Dragon's Dogma 2 Character Creator & Storage",
        "titleId": "PPSA09999_00",
        "platform": "PS5",
        "subscriptionService": "NONE",
    },
    {
        "name": "Prime Video",
        "titleId": "CUSA00119_00",
        "platform": "PS4",
        "subscriptionService": "NONE",
    },
    {
        "name": "Concord Beta",
        "titleId": "PPSA08888_00",
        "platform": "PS5",
        "subscriptionService": "NONE",
    },
    {
        "name": "FairGame$ Playtest",
        "titleId": "PPSA07777_00",
        "platform": "PS5",
        "subscriptionService": "NONE",
    },
    {
        # Not on any name list — only its played-titles category gives it away.
        "name": "Some Streaming Thing",
        "titleId": "CUSA55555_00",
        "platform": "PS4",
        "subscriptionService": "NONE",
    },
    {
        # Dutch storefront names: the localized Media Player app…
        "name": "Mediaspeler",
        "titleId": "CUSA44444_00",
        "platform": "PS4",
        "subscriptionService": "NONE",
    },
    {
        # …and the NLZIET streaming service.
        "name": "NLZIET",
        "titleId": "CUSA33333_00",
        "platform": "PS4",
        "subscriptionService": "NONE",
    },
]


@respx.mock
def test_non_games_pause_in_the_excluded_review_list(client):
    mock_psn(
        purchased=PURCHASED + JUNK,
        played=[{"titleId": "CUSA55555_00", "category": "media"}],
    )
    headers = auth_headers(client)
    job_id = start_job(client, headers)
    job = job_status(client, headers, job_id)

    assert job["status"] == "review"
    assert {c["name"] for c in job["candidates"]} == {"Returnal", "Bloodborne"}
    excluded = {e["name"]: e["reason"] for e in job["excluded"]}
    assert set(excluded) == {
        "Dragon's Dogma 2 Character Creator & Storage",
        "Prime Video",
        "Concord Beta",
        "FairGame$ Playtest",
        "Some Streaming Thing",
        "Mediaspeler",
        "NLZIET",
    }
    assert all(excluded.values())  # every exclusion explains itself

    # Nothing is created until the review is confirmed.
    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert items == []


@respx.mock
def test_confirm_imports_only_the_selected_titles(client):
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    job_id = start_job(client, headers)
    job = confirm(client, headers, job_id, ["PPSA01284"])

    assert counts(job) == {"imported": 1, "skipped": 0, "total": 1}
    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert [i["title"] for i in items] == ["Returnal"]


@respx.mock
def test_excluded_titles_can_be_rescued_at_confirm(client):
    mock_psn(purchased=PURCHASED + JUNK)
    headers = auth_headers(client)
    job_id = start_job(client, headers)
    job = confirm(client, headers, job_id, ["PPSA08888"])  # the Concord Beta

    assert job["imported"] == 1
    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert [i["title"] for i in items] == ["Concord Beta"]


@respx.mock
def test_confirm_requires_a_job_in_review(client):
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    job_id = start_job(client, headers)
    confirm(client, headers, job_id, ["PPSA01284"])

    res = client.post(
        f"/api/psn/import/{job_id}/confirm", json={"title_ids": []}, headers=headers
    )
    assert res.status_code == 409
    res = client.post(
        "/api/psn/import/nope/confirm", json={"title_ids": []}, headers=headers
    )
    assert res.status_code == 404


@respx.mock
def test_purchased_list_is_paginated(client):
    many = [
        {"name": f"Game {n}", "titleId": f"CUSA{n:05d}", "platform": "PS4",
         "image": {"url": f"https://cdn.psn.test/{n}.png"}}
        for n in range(120)
    ]
    mock_psn(purchased=many)
    headers = auth_headers(client)
    assert do_import(client, headers)["imported"] == 120


@respx.mock
def test_reimport_flags_previously_imported_titles(client):
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    assert do_import(client, headers)["imported"] == 2

    # Second run: both titles now exist in the library, so the review
    # pre-excludes them and nothing is imported.
    job_id = start_job(client, headers)
    review = job_status(client, headers, job_id)
    assert review["candidates"] == []
    assert {e["reason"] for e in review["excluded"]} == {"already in your collection"}

    job = confirm(client, headers, job_id, [])
    assert counts(job) == {"imported": 0, "skipped": 0, "total": 0}


@respx.mock
def test_manually_added_titles_are_flagged_as_already_owned(client):
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    # A manual physical copy, trademark glyph and all.
    create_item(client, headers, type="game", title="Returnal™", format="physical")

    job_id = start_job(client, headers)
    review = job_status(client, headers, job_id)
    assert [c["name"] for c in review["candidates"]] == ["Bloodborne"]
    flagged = next(e for e in review["excluded"] if e["name"] == "Returnal")
    assert flagged["reason"] == "already in your collection"

    # Rescuable: confirming it anyway imports the digital copy.
    job = confirm(client, headers, job_id, ["PPSA01284", "CUSA00207"])
    assert job["imported"] == 2


@respx.mock
def test_rejected_npsso_fails_the_job_with_a_clear_message(client):
    mock_psn(code_ok=False)
    headers = auth_headers(client)
    job = do_import(client, headers)
    assert job["status"] == "error"
    assert "NPSSO" in job["detail"]


def test_import_requires_auth(client):
    assert client.post("/api/psn/import", json={"npsso": "x" * 20}).status_code == 401


@respx.mock
def test_job_status_is_scoped_to_its_owner(client):
    mock_psn(purchased=PURCHASED)
    mine = auth_headers(client, email="job-owner@example.com")
    theirs = auth_headers(client, email="job-snoop@example.com")

    res = client.post(
        "/api/psn/import", json={"npsso": "npsso-cookie-value"}, headers=mine
    )
    job_id = res.json()["job_id"]
    assert client.get(f"/api/psn/import/{job_id}", headers=theirs).status_code == 404
    assert client.get("/api/psn/import/nope", headers=mine).status_code == 404


@respx.mock
def test_playtime_prefills_progress_hours(client):
    mock_psn(
        purchased=PURCHASED,
        played=[
            {"titleId": "PPSA01284_00", "playDuration": "PT62H30M"},
            {"titleId": "CUSA99999_00", "playDuration": "PT9H"},  # not owned
        ],
    )
    headers = auth_headers(client)
    do_import(client, headers)

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    by_title = {i["title"]: i for i in items}
    returnal = by_title["Returnal"]
    assert returnal["metadata"]["playtime_minutes"] == 3750
    assert float(returnal["progress_current"]) == 62.5
    # Never played: no fake zero-hour progress.
    assert by_title["Bloodborne"]["progress_current"] is None
    assert "playtime_minutes" not in by_title["Bloodborne"]["metadata"]


@respx.mock
def test_playtime_failure_does_not_block_the_import(client):
    mock_psn(purchased=PURCHASED)
    respx.get(GAMELIST_URL).mock(return_value=httpx.Response(403))
    headers = auth_headers(client)
    job = do_import(client, headers)
    assert job["status"] == "done"
    assert job["imported"] == 2


@respx.mock
def test_import_records_activity_events(client):
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    do_import(client, headers)

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    events = client.get(f"/api/items/{items[0]['id']}/activity", headers=headers).json()[
        "events"
    ]
    assert [e["event_type"] for e in events] == ["item_added"]
    assert events[0]["new_value"]["source"] == "psn_import"


@respx.mock
def test_pc_copies_do_not_block_playstation_imports(client):
    """The Epic/GOG copy of a game lives on PC; the PS5 entitlement is a
    different platform, so it stays importable with a note."""
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    create_item(
        client, headers, type="game", title="Returnal", format="digital",
        metadata={"platform": "PC (Microsoft Windows)", "epic_app_name": "x"},
    )

    job_id = start_job(client, headers)
    review = job_status(client, headers, job_id)
    returnal = next(c for c in review["candidates"] if c["name"] == "Returnal")
    assert returnal["note"] == "also owned on PC (Microsoft Windows)"
    assert returnal["reason"] is None


@respx.mock
def test_same_console_copy_is_still_excluded(client):
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    create_item(
        client, headers, type="game", title="Returnal", format="physical",
        metadata={"platform": "PlayStation 5"},
    )

    job_id = start_job(client, headers)
    review = job_status(client, headers, job_id)
    assert [c["name"] for c in review["candidates"]] == ["Bloodborne"]
    flagged = next(e for e in review["excluded"] if e["name"] == "Returnal")
    assert flagged["reason"] == "already in your collection"
