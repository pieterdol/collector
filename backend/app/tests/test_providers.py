"""Provider abstraction tests — external HTTP is mocked with respx."""

import httpx
import pytest
import respx

from app.config import get_settings
from app.db import SessionLocal
from app.domain.enums import ItemType
from app.providers import get_provider


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def keys(monkeypatch):
    """Set provider keys for a test and reset the settings cache."""

    def _set(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


OPENLIB_SEARCH = {
    "docs": [
        {
            "title": "Dune",
            "author_name": ["Frank Herbert"],
            "first_publish_year": 1965,
            "number_of_pages_median": 412,
            "publisher": ["Chilton Books"],
            "isbn": ["9780441172719"],
            "cover_i": 11481354,
        }
    ]
}


@respx.mock
def test_openlibrary_search_maps_results(db):
    respx.get("https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=OPENLIB_SEARCH)
    )
    provider = get_provider(ItemType.BOOK, db)
    assert provider.available
    results = provider.search("dune")
    assert len(results) == 1
    r = results[0]
    assert r.title == "Dune"
    assert r.item_type == ItemType.BOOK
    assert r.metadata["authors"] == ["Frank Herbert"]
    assert r.metadata["page_count"] == 412
    assert r.metadata["publisher"] == "Chilton Books"
    assert r.metadata["year"] == 1965
    assert "11481354" in r.cover_url


@respx.mock
def test_openlibrary_isbn_lookup(db):
    respx.get("https://openlibrary.org/api/books").mock(
        return_value=httpx.Response(
            200,
            json={
                "ISBN:9780441172719": {
                    "title": "Dune",
                    "authors": [{"name": "Frank Herbert"}],
                    "number_of_pages": 412,
                    "publishers": [{"name": "Chilton Books"}],
                    "publish_date": "1965",
                    "cover": {"large": "https://covers.openlibrary.org/b/id/11481354-L.jpg"},
                }
            },
        )
    )
    provider = get_provider(ItemType.BOOK, db)
    result = provider.lookup_barcode("9780441172719")
    assert result is not None
    assert result.title == "Dune"
    assert result.metadata["isbn"] == "9780441172719"
    assert result.metadata["authors"] == ["Frank Herbert"]


def test_tmdb_unavailable_without_key(db, keys):
    keys(TMDB_API_KEY="")
    provider = get_provider(ItemType.MOVIE, db)
    assert not provider.available
    assert provider.search("blade runner") == []


@respx.mock
def test_tmdb_search_maps_results(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 335984,
                        "title": "Blade Runner 2049",
                        "release_date": "2017-10-04",
                        "poster_path": "/poster.jpg",
                        "overview": "A young blade runner...",
                    }
                ]
            },
        )
    )
    provider = get_provider(ItemType.MOVIE, db)
    results = provider.search("blade runner")
    assert results[0].title == "Blade Runner 2049"
    assert results[0].metadata["year"] == 2017
    assert results[0].metadata["tmdb_id"] == 335984
    assert results[0].cover_url == "https://image.tmdb.org/t/p/w500/poster.jpg"


@respx.mock
def test_tmdb_details_adds_director_and_runtime(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/movie/335984").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 335984,
                "title": "Blade Runner 2049",
                "release_date": "2017-10-04",
                "runtime": 164,
                "poster_path": "/poster.jpg",
                "credits": {
                    "crew": [
                        {"job": "Producer", "name": "Someone Else"},
                        {"job": "Director", "name": "Denis Villeneuve"},
                    ]
                },
            },
        )
    )
    provider = get_provider(ItemType.MOVIE, db)
    result = provider.details("335984")
    assert result.metadata["director"] == "Denis Villeneuve"
    assert result.metadata["runtime"] == 164


@respx.mock
def test_igdb_fetches_token_then_searches(db, keys):
    keys(TWITCH_CLIENT_ID="cid", TWITCH_CLIENT_SECRET="secret")
    token_route = respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok", "expires_in": 5000}
        )
    )
    respx.post("https://api.igdb.com/v4/games").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1942,
                    "name": "Hollow Knight",
                    "first_release_date": 1487894400,
                    "platforms": [{"name": "PC"}, {"name": "Switch"}],
                    "involved_companies": [
                        {"developer": True, "company": {"name": "Team Cherry"}}
                    ],
                    "cover": {"image_id": "co1rgi"},
                }
            ],
        )
    )
    provider = get_provider(ItemType.GAME, db)
    assert provider.available
    results = provider.search("hollow knight")
    assert token_route.called
    r = results[0]
    assert r.title == "Hollow Knight"
    assert r.metadata["igdb_id"] == 1942
    assert r.metadata["developer"] == "Team Cherry"
    assert r.metadata["platform"] == "PC, Switch"
    assert r.metadata["year"] == 2017
    assert "co1rgi" in r.cover_url


@respx.mock
def test_search_results_are_cached(db):
    route = respx.get("https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=OPENLIB_SEARCH)
    )
    provider = get_provider(ItemType.BOOK, db)
    provider.search("dune")
    provider.search("dune")
    assert route.call_count == 1  # second hit served from provider_cache


@respx.mock
def test_expired_cache_is_refetched(db, monkeypatch):
    route = respx.get("https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=OPENLIB_SEARCH)
    )
    provider = get_provider(ItemType.BOOK, db)
    provider.search("dune")

    from datetime import UTC, datetime, timedelta

    from app.models import ProviderCache

    for row in db.query(ProviderCache).all():
        row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()

    get_provider(ItemType.BOOK, db).search("dune")
    assert route.call_count == 2


@respx.mock
def test_provider_error_degrades_to_empty_results(db):
    respx.get("https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(500)
    )
    provider = get_provider(ItemType.BOOK, db)
    assert provider.search("dune") == []
