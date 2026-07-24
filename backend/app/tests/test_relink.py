"""Relink: point an item at a different catalog record — the escape
hatch for wrong or missing automatic metadata matches."""

import httpx
import pytest
import respx

from app.config import get_settings
from app.tests.helpers import auth_headers, create_item

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c626001000000ffff03000006000557"
    "bfabd40000000049454e44ae426082"
)


@pytest.fixture
def twitch(monkeypatch):
    monkeypatch.setenv("TWITCH_CLIENT_ID", "cid")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "sec")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


DETAILS_GAME = {
    "id": 119171,
    "name": "God of War Ragnarök",
    "summary": "Fimbulwinter is well underway.",
    "first_release_date": 1667952000,
    "cover": {"image_id": "gowr"},
    "involved_companies": [
        {"developer": True, "company": {"name": "Santa Monica Studio"}}
    ],
}


def mock_igdb(details_game=DETAILS_GAME):
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 9999})
    )

    def route(request):
        body = request.content.decode()
        if "artworks.image_id" in body:  # the artwork refetch after relinking
            return httpx.Response(
                200,
                json=[{"id": 119171, "artworks": [{"image_id": "art1"}], "screenshots": []}]
                if details_game else [],
            )
        return httpx.Response(200, json=[details_game] if details_game else [])

    respx.post("https://api.igdb.com/v4/games").mock(side_effect=route)
    respx.get(url__regex=r"https://images\.igdb\.com/.*").mock(
        return_value=httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    )


@respx.mock
def test_relink_replaces_metadata_but_keeps_import_provenance(client, twitch):
    mock_igdb()
    headers = auth_headers(client)
    item = create_item(
        client, headers, type="game", title="God of War Ragnarok", format="digital",
        metadata={
            "psn_title_id": "PPSA01284",
            "storefront": "PlayStation Store",
            "platform": "PlayStation 5",
            "playtime_minutes": 300,
            "igdb_id": 999,  # the wrong auto-match being corrected
            "description": "Wrong game's description",
            "artwork_fetched": True,
        },
    )

    res = client.post(
        f"/api/items/{item['id']}/relink", json={"external_id": "119171"}, headers=headers
    )
    assert res.status_code == 200, res.text
    meta = res.json()["metadata"]

    assert meta["igdb_id"] == 119171
    assert meta["description"] == "Fimbulwinter is well underway."
    assert meta["developer"] == "Santa Monica Studio"
    assert meta["release_date"] == "2022-11-09"
    # Import provenance and user data survive the swap.
    assert meta["psn_title_id"] == "PPSA01284"
    assert meta["storefront"] == "PlayStation Store"
    assert meta["platform"] == "PlayStation 5"
    assert meta["playtime_minutes"] == 300
    # Artwork was refetched for the new game.
    assert meta["artwork_fetched"] is True
    assert meta["hero_path"].endswith("hero.png")
    assert res.json()["cover_path"] is not None
    # Title is the user's; relinking doesn't rename.
    assert res.json()["title"] == "God of War Ragnarok"


@respx.mock
def test_relink_unknown_id_is_a_404(client, twitch):
    mock_igdb(details_game=None)
    headers = auth_headers(client)
    item = create_item(client, headers, type="game", title="Something", format="digital")
    res = client.post(
        f"/api/items/{item['id']}/relink", json={"external_id": "424242"}, headers=headers
    )
    assert res.status_code == 404


def test_relink_requires_auth(client):
    assert client.post(
        "/api/items/00000000-0000-0000-0000-000000000000/relink",
        json={"external_id": "1"},
    ).status_code == 401
