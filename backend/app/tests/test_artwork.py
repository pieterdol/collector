"""Artwork enrichment: hero image, screenshots, description — fetched once."""

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
def keys(monkeypatch):
    def _set(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


def png_response(*_args, **_kwargs):
    return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})


APPDETAILS = {
    "367520": {
        "success": True,
        "data": {
            "short_description": "Forge your own path in Hallownest.",
            "release_date": {"coming_soon": False, "date": "24 Feb, 2017"},
            "screenshots": [
                {"id": i, "path_full": f"https://cdn.example.com/shots/{i}.png"}
                for i in range(7)
            ],
        },
    }
}


@respx.mock
def test_steam_game_gets_hero_shots_and_description(client):
    respx.get("https://store.steampowered.com/api/appdetails").mock(
        return_value=httpx.Response(200, json=APPDETAILS)
    )
    respx.get(url__regex=r"https://cdn\.cloudflare\.steamstatic\.com/.*library_hero\.jpg").mock(
        side_effect=png_response
    )
    respx.get(url__regex=r"https://cdn\.example\.com/shots/.*").mock(side_effect=png_response)

    headers = auth_headers(client)
    item = create_item(
        client, headers, type="game", title="Hollow Knight", format="digital",
        metadata={"steam_appid": 367520},
    )
    res = client.post(f"/api/items/{item['id']}/artwork", headers=headers)
    assert res.status_code == 200, res.text
    meta = res.json()["metadata"]
    assert meta["artwork_fetched"] is True
    assert meta["description"] == "Forge your own path in Hallownest."
    assert meta["release_date"] == "2017-02-24"
    assert meta["hero_path"] == f"/media/artwork/{item['id']}/hero.png"
    assert len(meta["screenshot_paths"]) == 5  # capped
    for path in meta["screenshot_paths"]:
        assert path.startswith(f"/media/artwork/{item['id']}/")

    from pathlib import Path

    art_dir = Path(get_settings().media_dir) / "artwork" / item["id"]
    assert (art_dir / "hero.png").read_bytes() == PNG


@respx.mock
def test_second_call_is_a_noop(client):
    route = respx.get("https://store.steampowered.com/api/appdetails").mock(
        return_value=httpx.Response(200, json=APPDETAILS)
    )
    respx.get(url__regex=r"https://.*").mock(side_effect=png_response)
    headers = auth_headers(client)
    item = create_item(client, headers, type="game", title="HK", format="digital",
                       metadata={"steam_appid": 367520})
    client.post(f"/api/items/{item['id']}/artwork", headers=headers)
    calls_after_first = route.call_count
    res = client.post(f"/api/items/{item['id']}/artwork", headers=headers)
    assert res.status_code == 200
    assert route.call_count == calls_after_first  # nothing refetched


@respx.mock
def test_movie_uses_tmdb_backdrops(client, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/movie/335984/images").mock(
        return_value=httpx.Response(
            200,
            json={"backdrops": [{"file_path": f"/b{i}.jpg"} for i in range(6)]},
        )
    )
    respx.get(url__regex=r"https://image\.tmdb\.org/t/p/.*").mock(side_effect=png_response)
    headers = auth_headers(client)
    item = create_item(
        client, headers, type="movie", title="BR2049", format="physical",
        metadata={"tmdb_id": 335984, "overview": "A young blade runner..."},
    )
    res = client.post(f"/api/items/{item['id']}/artwork", headers=headers)
    meta = res.json()["metadata"]
    assert meta["hero_path"].endswith("hero.png")
    assert len(meta["screenshot_paths"]) == 5
    assert meta["description"] == "A young blade runner..."  # overview reused


@respx.mock
def test_igdb_game_without_steam_uses_igdb(client, keys):
    keys(TWITCH_CLIENT_ID="cid", TWITCH_CLIENT_SECRET="sec")
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 9999})
    )
    respx.post("https://api.igdb.com/v4/games").mock(
        return_value=httpx.Response(
            200,
            json=[{
                "id": 119133,
                "summary": "An action RPG in the Lands Between.",
                "artworks": [{"image_id": "art1"}],
                "screenshots": [{"image_id": f"sc{i}"} for i in range(3)],
            }],
        )
    )
    respx.get(url__regex=r"https://images\.igdb\.com/.*").mock(side_effect=png_response)
    headers = auth_headers(client)
    item = create_item(client, headers, type="game", title="Elden Ring", format="physical",
                       metadata={"igdb_id": 119133})
    res = client.post(f"/api/items/{item['id']}/artwork", headers=headers)
    meta = res.json()["metadata"]
    assert meta["description"] == "An action RPG in the Lands Between."
    assert meta["hero_path"].endswith("hero.png")
    assert len(meta["screenshot_paths"]) == 3


def test_book_marks_fetched_without_network(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="book", title="Dune")
    res = client.post(f"/api/items/{item['id']}/artwork", headers=headers)
    meta = res.json()["metadata"]
    assert meta["artwork_fetched"] is True
    assert "hero_path" not in meta


@respx.mock
def test_provider_failure_leaves_item_retryable(client):
    respx.get("https://store.steampowered.com/api/appdetails").mock(
        return_value=httpx.Response(500)
    )
    headers = auth_headers(client)
    item = create_item(client, headers, type="game", title="HK", format="digital",
                       metadata={"steam_appid": 367520})
    res = client.post(f"/api/items/{item['id']}/artwork", headers=headers)
    assert res.status_code == 200
    # not marked fetched, so a later attempt can retry
    assert "artwork_fetched" not in res.json()["metadata"]
