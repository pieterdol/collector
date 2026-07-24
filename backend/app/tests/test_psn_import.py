"""PSN import: exchange an NPSSO cookie for a token, pull the purchased
list, and keep PS Plus-gated titles out unless explicitly included."""

import json

import httpx
import respx

from app.providers.psn import AUTH_BASE, GRAPHQL_URL
from app.tests.helpers import auth_headers

REDIRECT = "com.scee.psxandroid.scecompcall://redirect?code=v3.AbCdEf"

PURCHASED = [
    {
        "name": "Returnal",
        "titleId": "PPSA01284",
        "platform": "PS5",
        "image": {"url": "https://cdn.psn.test/returnal.png"},
    },
    {
        "name": "Bloodborne",
        "titleId": "CUSA00207",
        "platform": "PS4",
        "image": {"url": "https://cdn.psn.test/bloodborne.png"},
    },
]

PS_PLUS = [
    {
        "name": "Stray",
        "titleId": "PPSA04640",
        "platform": "PS5",
        "image": {"url": "https://cdn.psn.test/stray.png"},
    },
]


def mock_psn(purchased=None, ps_plus=None, code_ok=True):
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

    def graphql(request):
        variables = json.loads(request.content)["variables"]
        games = purchased if variables["subscriptionService"] == "NONE" else ps_plus
        games = games or []
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


def do_import(client, headers, **body):
    return client.post(
        "/api/psn/import", json={"npsso": "npsso-cookie-value", **body}, headers=headers
    )


@respx.mock
def test_import_excludes_ps_plus_by_default(client):
    mock_psn(purchased=PURCHASED, ps_plus=PS_PLUS)
    headers = auth_headers(client)
    res = do_import(client, headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"imported": 2, "skipped": 0, "total": 2}

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
    res = do_import(client, headers, include_ps_plus=True)
    assert res.json() == {"imported": 3, "skipped": 0, "total": 3}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    stray = next(i for i in items if i["title"] == "Stray")
    assert stray["metadata"]["subscription"] == "PS Plus"


@respx.mock
def test_purchased_list_is_paginated(client):
    many = [
        {"name": f"Game {n}", "titleId": f"CUSA{n:05d}", "platform": "PS4",
         "image": {"url": f"https://cdn.psn.test/{n}.png"}}
        for n in range(120)
    ]
    mock_psn(purchased=many)
    headers = auth_headers(client)
    res = do_import(client, headers)
    assert res.json()["imported"] == 120


@respx.mock
def test_reimport_skips_existing_titles(client):
    mock_psn(purchased=PURCHASED)
    headers = auth_headers(client)
    assert do_import(client, headers).json()["imported"] == 2

    res = do_import(client, headers)
    assert res.json() == {"imported": 0, "skipped": 2, "total": 2}


@respx.mock
def test_rejected_npsso_is_a_clear_401(client):
    mock_psn(code_ok=False)
    headers = auth_headers(client)
    res = do_import(client, headers)
    assert res.status_code == 401
    assert "NPSSO" in res.json()["detail"]


def test_import_requires_auth(client):
    assert client.post("/api/psn/import", json={"npsso": "x" * 20}).status_code == 401


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
