import httpx
import pytest
import respx

from app.config import get_settings
from app.db import SessionLocal
from app.models import Platform
from app.tests.helpers import auth_headers, create_item
from app.tests.test_music_providers import KID_A_SEARCH
from app.tests.test_providers import OPENLIB_SEARCH


@pytest.fixture
def keys(monkeypatch):
    def _set(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


def test_enrich_requires_auth(client):
    assert client.get("/api/enrich/search?type=book&q=dune").status_code == 401


@respx.mock
def test_enrich_search_returns_provider_results(client):
    respx.get("https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=OPENLIB_SEARCH)
    )
    headers = auth_headers(client)
    res = client.get("/api/enrich/search?type=book&q=dune", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "openlibrary"
    assert body["available"] is True
    assert body["results"][0]["title"] == "Dune"
    assert body["results"][0]["metadata"]["authors"] == ["Frank Herbert"]


def test_enrich_search_movie_without_key_degrades(client):
    headers = auth_headers(client)
    res = client.get("/api/enrich/search?type=movie&q=arrival", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert body["results"] == []


@respx.mock
def test_enrich_search_narrows_games_to_the_chosen_platform(client, keys):
    keys(TWITCH_CLIENT_ID="cid", TWITCH_CLIENT_SECRET="secret")
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 5000})
    )
    with SessionLocal() as db:
        db.add(Platform(igdb_id=167, name="PlayStation 5"))
        db.commit()
    route = respx.post("https://api.igdb.com/v4/games").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 3, "name": "Astro Bot", "platforms": [{"name": "PlayStation 5"}]}],
        )
    )
    res = client.get(
        "/api/enrich/search?type=game&q=astro&platform=PlayStation+5",
        headers=auth_headers(client),
    )
    assert res.status_code == 200
    assert res.json()["results"][0]["title"] == "Astro Bot"
    assert "where platforms = (167)" in route.calls[0].request.content.decode()


def test_enrich_search_platform_filter_is_ignored_for_books(client):
    """Only games can be narrowed — a stray param must not break other types."""
    res = client.get(
        "/api/enrich/search?type=movie&q=arrival&platform=PlayStation+5",
        headers=auth_headers(client),
    )
    assert res.status_code == 200
    assert res.json()["results"] == []


@respx.mock
def test_barcode_isbn_returns_book_match(client):
    respx.get("https://openlibrary.org/api/books").mock(
        return_value=httpx.Response(
            200,
            json={
                "ISBN:9780441172719": {
                    "title": "Dune",
                    "authors": [{"name": "Frank Herbert"}],
                    "number_of_pages": 412,
                }
            },
        )
    )
    headers = auth_headers(client)
    res = client.get("/api/enrich/barcode?code=9780441172719", headers=headers)
    body = res.json()
    assert body["matched"] is True
    assert body["kind"] == "isbn"
    assert body["result"]["title"] == "Dune"


@respx.mock
def test_barcode_upc_matches_a_music_release(client):
    """Sleeve barcodes are the one UPC family with a public catalog."""
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json=KID_A_SEARCH)
    )
    res = client.get("/api/enrich/barcode?code=724352773824", headers=auth_headers(client))
    body = res.json()
    assert body["matched"] is True
    assert body["kind"] == "upc"
    assert body["result"]["title"] == "Kid A"
    assert body["result"]["type"] == "music"


@respx.mock
def test_barcode_upc_without_a_music_match_is_captured_unmatched(client):
    """Discs and game boxes have no public barcode catalog — store the code."""
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json={"count": 0, "releases": []})
    )
    res = client.get("/api/enrich/barcode?code=883929247318", headers=auth_headers(client))
    body = res.json()
    assert body["matched"] is False
    assert body["kind"] == "upc"
    assert body["code"] == "883929247318"


@respx.mock
def test_barcode_upc_survives_a_provider_outage(client):
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(503)
    )
    res = client.get("/api/enrich/barcode?code=883929247318", headers=auth_headers(client))
    assert res.status_code == 200
    assert res.json()["matched"] is False


@respx.mock
def test_barcode_reports_a_book_already_in_the_collection(client):
    """Scanning a copy you already added must not start a second one."""
    route = respx.get("https://openlibrary.org/api/books")
    headers = auth_headers(client)
    item = create_item(
        client, headers, metadata={"authors": ["Frank Herbert"], "isbn": "9780441172719"}
    )
    res = client.get("/api/enrich/barcode?code=978-0-441-17271-9", headers=headers)
    body = res.json()
    assert body["owned_item_id"] == item["id"]
    assert body["code"] == "9780441172719"
    assert body["kind"] == "isbn"
    assert not route.called  # a hit skips the catalog entirely


@respx.mock
def test_barcode_matches_the_other_isbn_form(client):
    """Books added by title search carry an ISBN-10; the barcode is the 13."""
    headers = auth_headers(client)
    item = create_item(client, headers, metadata={"isbn": "0441172717"})
    res = client.get("/api/enrich/barcode?code=9780441172719", headers=headers)
    assert res.json()["owned_item_id"] == item["id"]


@respx.mock
def test_barcode_matches_a_sleeve_barcode_stored_with_spaces(client):
    """Catalogs report sleeve barcodes as printed ("7 24352 77382 4")."""
    headers = auth_headers(client)
    item = create_item(
        client,
        headers,
        type="music",
        title="Kid A",
        metadata={"artist": "Radiohead", "barcode": "7 24352 77382 4"},
    )
    res = client.get("/api/enrich/barcode?code=724352773824", headers=headers)
    assert res.json()["owned_item_id"] == item["id"]


@respx.mock
def test_barcode_matches_a_code_captured_without_a_catalog_match(client):
    """Movies and games store the raw scan as `upc` — that counts as owned."""
    headers = auth_headers(client)
    item = create_item(
        client, headers, type="movie", title="Arrival", metadata={"upc": "883929247318"}
    )
    res = client.get("/api/enrich/barcode?code=883929247318", headers=headers)
    assert res.json()["owned_item_id"] == item["id"]


@respx.mock
def test_barcode_ignores_another_users_copy(client):
    """Owned means owned by you — someone else's ISBN is not your item."""
    respx.get("https://openlibrary.org/api/books").mock(
        return_value=httpx.Response(
            200, json={"ISBN:9780441172719": {"title": "Dune", "authors": []}}
        )
    )
    theirs = auth_headers(client, email="other@example.com", name="Other")
    create_item(client, theirs, metadata={"isbn": "9780441172719"})
    mine = auth_headers(client)
    res = client.get("/api/enrich/barcode?code=9780441172719", headers=mine)
    body = res.json()
    assert body["owned_item_id"] is None
    assert body["matched"] is True  # falls through to the catalog as usual


def test_providers_status_lists_all(client):
    headers = auth_headers(client)
    res = client.get("/api/enrich/providers", headers=headers)
    body = {p["type"]: p for p in res.json()["providers"]}
    assert body["book"]["available"] is True  # Open Library needs no key
    assert body["movie"]["available"] is False
    assert body["tv"]["available"] is False  # TMDB, reported distinctly from movies
    assert body["game"]["available"] is False
    # MusicBrainz needs no key either, so music search works out of the box.
    assert body["music"]["available"] is True
    assert body["music"]["name"] == "musicbrainz"
