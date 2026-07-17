"""Platform records: linking on create/patch, IGDB catalog sync."""

import httpx
import pytest
import respx
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Platform
from app.tests.helpers import auth_headers, create_item


@pytest.fixture
def keys(monkeypatch):
    def _set(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


def platform_rows() -> list[Platform]:
    with SessionLocal() as db:
        return list(db.scalars(select(Platform).order_by(Platform.name)))


def test_creating_a_game_links_a_platform_row(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="game", title="Wolfenstein",
                       metadata={"platform": "Xbox One"})
    assert item["platform"] == "Xbox One"
    rows = platform_rows()
    assert [p.name for p in rows] == ["Xbox One"]
    assert rows[0].igdb_id is None  # custom row until the catalog sync


def test_same_platform_name_reuses_the_row_case_insensitively(client):
    headers = auth_headers(client)
    create_item(client, headers, type="game", title="A", metadata={"platform": "Xbox One"})
    create_item(client, headers, type="game", title="B", metadata={"platform": "xbox one"})
    assert len(platform_rows()) == 1


def test_patching_platform_relinks(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="game", title="Wolfenstein",
                       metadata={"platform": "Xbox One"})
    res = client.patch(
        f"/api/items/{item['id']}",
        json={"metadata": {"platform": "Xbox Series X|S"}},
        headers=headers,
    )
    assert res.json()["platform"] == "Xbox Series X|S"
    assert {p.name for p in platform_rows()} == {"Xbox One", "Xbox Series X|S"}


def test_books_get_no_platform_link(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="book", title="Dune")
    assert item["platform"] is None
    assert platform_rows() == []


@respx.mock
def test_platform_catalog_syncs_from_igdb_once(client, keys):
    keys(TWITCH_CLIENT_ID="cid", TWITCH_CLIENT_SECRET="sec")
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 9999})
    )
    catalog = respx.post("https://api.igdb.com/v4/platforms").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 49, "name": "Xbox One", "abbreviation": "XONE"},
                {"id": 130, "name": "Nintendo Switch", "abbreviation": "Switch"},
                {"id": 167, "name": "PlayStation 5", "abbreviation": "PS5"},
            ],
        )
    )
    headers = auth_headers(client)
    # a custom row exists already (from a game added before the sync)
    create_item(client, headers, type="game", title="W", metadata={"platform": "Xbox One"})

    res = client.get("/api/platforms", headers=headers)
    names = [p["name"] for p in res.json()["platforms"]]
    assert names == ["Nintendo Switch", "PlayStation 5", "Xbox One"]
    # the pre-existing custom row got its IGDB id attached, not duplicated
    xbox = next(p for p in platform_rows() if p.name == "Xbox One")
    assert xbox.igdb_id == 49
    assert catalog.call_count == 1


def test_platform_catalog_without_credentials_returns_custom_rows(client):
    headers = auth_headers(client)
    create_item(client, headers, type="game", title="W", metadata={"platform": "PC (Steam)"})
    res = client.get("/api/platforms", headers=headers)
    assert [p["name"] for p in res.json()["platforms"]] == ["PC (Steam)"]
