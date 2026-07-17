import httpx
import pytest
import respx

from app.config import get_settings
from app.tests.helpers import auth_headers

OWNED_GAMES = {
    "response": {
        "game_count": 2,
        "games": [
            {"appid": 367520, "name": "Hollow Knight", "playtime_forever": 1860},
            {"appid": 413150, "name": "Stardew Valley", "playtime_forever": 0},
        ],
    }
}


@pytest.fixture
def steam_key(monkeypatch):
    monkeypatch.setenv("STEAM_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def mock_owned_games(stub_cdn=True):
    if stub_cdn:
        # The import's background task fetches covers from the Steam CDN;
        # stub it with 404 so cover-less tests stay focused.
        respx.get(url__regex=r"https://cdn\.cloudflare\.steamstatic\.com/.*").mock(
            return_value=httpx.Response(404)
        )
    return respx.get(
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    ).mock(return_value=httpx.Response(200, json=OWNED_GAMES))


@respx.mock
def test_import_creates_digital_games_with_playtime(client, steam_key):
    mock_owned_games()
    headers = auth_headers(client)
    res = client.post(
        "/api/steam/import", json={"steam_id": "76561198000000001"}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"imported": 2, "skipped": 0, "total": 2}

    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    by_title = {i["title"]: i for i in items}
    hollow = by_title["Hollow Knight"]
    assert hollow["format"] == "digital"
    assert hollow["status"] == "backlog"
    assert hollow["metadata"]["steam_appid"] == 367520
    assert hollow["metadata"]["playtime_minutes"] == 1860
    assert hollow["metadata"]["platform"] == "PC (Steam)"
    assert float(hollow["progress_current"]) == 31.0  # hours

    stardew = by_title["Stardew Valley"]
    assert stardew["progress_current"] is None
    assert stardew["metadata"]["playtime_minutes"] == 0


@respx.mock
def test_reimport_dedupes_on_steam_appid(client, steam_key):
    mock_owned_games()
    headers = auth_headers(client)
    client.post("/api/steam/import", json={"steam_id": "76561198000000001"}, headers=headers)
    res = client.post(
        "/api/steam/import", json={"steam_id": "76561198000000001"}, headers=headers
    )
    assert res.json() == {"imported": 0, "skipped": 2, "total": 2}
    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert len(items) == 2


@respx.mock
def test_vanity_url_is_resolved(client, steam_key):
    respx.get(
        "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
    ).mock(
        return_value=httpx.Response(
            200, json={"response": {"success": 1, "steamid": "76561198000000001"}}
        )
    )
    mock_owned_games()
    headers = auth_headers(client)
    res = client.post("/api/steam/import", json={"steam_id": "gaben"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["imported"] == 2


@respx.mock
def test_unknown_vanity_is_404(client, steam_key):
    respx.get(
        "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
    ).mock(return_value=httpx.Response(200, json={"response": {"success": 42}}))
    headers = auth_headers(client)
    res = client.post("/api/steam/import", json={"steam_id": "nobody"}, headers=headers)
    assert res.status_code == 404


def test_missing_key_gives_503(client):
    headers = auth_headers(client)
    res = client.post(
        "/api/steam/import", json={"steam_id": "76561198000000001"}, headers=headers
    )
    assert res.status_code == 503


@respx.mock
def test_private_profile_gives_clear_error(client, steam_key):
    respx.get(
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    ).mock(return_value=httpx.Response(200, json={"response": {}}))
    headers = auth_headers(client)
    res = client.post(
        "/api/steam/import", json={"steam_id": "76561198000000001"}, headers=headers
    )
    assert res.status_code == 400
    assert "private" in res.json()["detail"].lower()


@respx.mock
def test_covers_are_fetched_in_background(client, steam_key):
    mock_owned_games(stub_cdn=False)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c626001000000ffff03000006000557"
        "bfabd40000000049454e44ae426082"
    )
    respx.get(url__regex=r"https://cdn\.cloudflare\.steamstatic\.com/steam/apps/\d+/library_600x900\.jpg").mock(
        return_value=httpx.Response(200, content=png, headers={"content-type": "image/png"})
    )
    headers = auth_headers(client)
    client.post("/api/steam/import", json={"steam_id": "76561198000000001"}, headers=headers)
    # TestClient runs FastAPI background tasks before returning, so covers exist now.
    items = client.get("/api/items?type=game", headers=headers).json()["items"]
    assert all(i["cover_path"] for i in items)
