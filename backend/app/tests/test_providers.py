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


@pytest.mark.parametrize("item_type", [ItemType.MOVIE, ItemType.TV])
def test_tmdb_unavailable_without_key(db, keys, item_type):
    keys(TMDB_API_KEY="")
    provider = get_provider(item_type, db)
    assert not provider.available
    assert provider.search("blade runner") == []


@respx.mock
def test_tmdb_movie_search_maps_results(db, keys):
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
    assert results[0].metadata["release_date"] == "2017-10-04"
    assert results[0].metadata["tmdb_id"] == 335984
    assert results[0].cover_url == "https://image.tmdb.org/t/p/w500/poster.jpg"


@respx.mock
def test_tmdb_tv_search_maps_results(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 1396,
                        "name": "Breaking Bad",
                        "first_air_date": "2008-01-20",
                        "poster_path": "/poster.jpg",
                        "overview": "When Walter White, a New Mexico chemistry teacher...",
                    }
                ]
            },
        )
    )
    provider = get_provider(ItemType.TV, db)
    results = provider.search("breaking bad")
    assert results[0].title == "Breaking Bad"
    assert results[0].metadata["year"] == 2008
    assert results[0].metadata["release_date"] == "2008-01-20"
    assert results[0].metadata["tmdb_id"] == 1396
    assert results[0].cover_url == "https://image.tmdb.org/t/p/w500/poster.jpg"


@respx.mock
def test_tmdb_search_orders_by_popularity(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"id": 1, "name": "Obscure Spinoff", "popularity": 3.2},
                    {"id": 2, "name": "The Hit Show", "popularity": 88.7},
                    {"id": 3, "name": "Mid Show", "popularity": 40.0},
                ]
            },
        )
    )
    provider = get_provider(ItemType.TV, db)
    titles = [r.title for r in provider.search("show")]
    assert titles == ["The Hit Show", "Mid Show", "Obscure Spinoff"]


@respx.mock
def test_tmdb_movie_and_tv_search_do_not_share_cache(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 111, "title": "Lost (the movie)"}]}
        )
    )
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 222, "name": "Lost (the show)"}]}
        )
    )
    # Same query, same provider name ("tmdb"): the endpoints must not
    # collide in provider_cache, or TV reads movie rows (title vs name)
    # and every title degrades to "Unknown".
    movie = get_provider(ItemType.MOVIE, db).search("lost")
    tv = get_provider(ItemType.TV, db).search("lost")
    assert movie[0].title == "Lost (the movie)"
    assert tv[0].title == "Lost (the show)"


@respx.mock
def test_tmdb_movie_details_adds_director_and_runtime(db, keys):
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
def test_tmdb_tv_details_adds_episode_runtime(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/tv/1399").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 1399,
                "name": "Game of Thrones",
                "first_air_date": "2011-04-17",
                "episode_run_time": [60],
                "poster_path": "/poster.jpg",
                "created_by": [
                    {"name": "David Benioff"},
                    {"name": "D.B. Weiss"},
                ],
                "number_of_episodes": 73,
                "number_of_seasons": 8,
            },
        )
    )
    provider = get_provider(ItemType.TV, db)
    result = provider.details("1399")
    assert result.metadata["director"] == "David Benioff"
    assert result.metadata["episode_runtime"] == 60
    assert result.metadata["number_of_episodes"] == 73
    assert result.metadata["number_of_seasons"] == 8


@respx.mock
def test_tmdb_details_capture_rating(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/movie/335984").mock(
        return_value=httpx.Response(
            200,
            json={"id": 335984, "title": "Blade Runner 2049", "vote_average": 8.456},
        )
    )
    respx.get("https://api.themoviedb.org/3/tv/1399").mock(
        return_value=httpx.Response(
            200,
            json={"id": 1399, "name": "Game of Thrones", "vote_average": 8.4},
        )
    )
    movie = get_provider(ItemType.MOVIE, db).details("335984")
    tv = get_provider(ItemType.TV, db).details("1399")
    assert movie.metadata["tmdb_rating"] == 8.5  # rounded to one decimal
    assert tv.metadata["tmdb_rating"] == 8.4


@respx.mock
def test_tmdb_details_treats_unrated_as_none(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/movie/42").mock(
        return_value=httpx.Response(
            200,
            json={"id": 42, "title": "Obscure Film", "vote_average": 0},
        )
    )
    result = get_provider(ItemType.MOVIE, db).details("42")
    assert result.metadata["tmdb_rating"] is None


@respx.mock
def test_tmdb_tv_details_captures_seasons(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/tv/1399").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 1399,
                "name": "Game of Thrones",
                "first_air_date": "2011-04-17",
                "number_of_seasons": 2,
                "seasons": [
                    {"id": 3624, "season_number": 0, "name": "Specials",
                     "episode_count": 14, "air_date": "2010-12-05",
                     "poster_path": "/s0.jpg", "vote_average": 0},
                    {"id": 3627, "season_number": 1, "name": "Season 1",
                     "episode_count": 10, "air_date": "2011-04-17",
                     "poster_path": "/s1.jpg", "vote_average": 8.3},
                    {"id": 3625, "season_number": 2, "name": "Season 2",
                     "episode_count": 10, "air_date": None,
                     "poster_path": None},
                ],
            },
        )
    )
    provider = get_provider(ItemType.TV, db)
    result = provider.details("1399")
    seasons = result.metadata["seasons"]
    assert [s["season_number"] for s in seasons] == [0, 1, 2]
    assert seasons[1] == {
        "tmdb_season_id": 3627,
        "season_number": 1,
        "name": "Season 1",
        "episode_count": 10,
        "air_date": "2011-04-17",
        "poster_path": "/s1.jpg",
    }
    assert seasons[2]["air_date"] is None


@respx.mock
def test_tmdb_tv_details_defaults_missing_counts_to_none(db, keys):
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/tv/999").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 999,
                "name": "Sparse Show",
                "first_air_date": "2020-01-01",
            },
        )
    )
    provider = get_provider(ItemType.TV, db)
    result = provider.details("999")
    assert result.metadata["episode_runtime"] is None
    assert result.metadata["number_of_episodes"] is None
    assert result.metadata["number_of_seasons"] is None


@respx.mock
def test_tmdb_tv_details_handles_empty_episode_runtime_list(db, keys):
    """Ongoing shows often report episode_run_time as [] — must not crash."""
    keys(TMDB_API_KEY="k")
    respx.get("https://api.themoviedb.org/3/tv/888").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 888,
                "name": "Ongoing Show",
                "first_air_date": "2023-01-01",
                "episode_run_time": [],
            },
        )
    )
    provider = get_provider(ItemType.TV, db)
    result = provider.details("888")
    assert result.metadata["episode_runtime"] is None


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
    assert r.metadata["release_date"] == "2017-02-24"
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


@respx.mock
def test_isbn_lookup_falls_back_to_isbn_cover_url(db):
    """Editions without a linked cover still get the covers-by-ISBN URL."""
    respx.get("https://openlibrary.org/api/books").mock(
        return_value=httpx.Response(
            200,
            json={
                "ISBN:9780141016405": {
                    "title": "Purple Cow",
                    "authors": [{"name": "Seth Godin"}],
                    "number_of_pages": 160,
                }
            },
        )
    )
    provider = get_provider(ItemType.BOOK, db)
    result = provider.lookup_barcode("9780141016405")
    assert result.cover_url == "https://covers.openlibrary.org/b/isbn/9780141016405-L.jpg?default=false"


@respx.mock
def test_igdb_maps_steam_appids_to_covers(db, keys):
    keys(TWITCH_CLIENT_ID="cid", TWITCH_CLIENT_SECRET="sec")
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 9999})
    )
    respx.post("https://api.igdb.com/v4/external_games").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "uid": "21090", "game": {"id": 123, "cover": {"id": 9, "image_id": "co1fear"}}},
                {"id": 2, "uid": "400", "game": {"id": 456}},  # game without cover art
            ],
        )
    )
    from app.providers.igdb import covers_for_steam_appids

    out = covers_for_steam_appids(db, [21090, 400, 99999])
    assert out == {
        21090: "https://images.igdb.com/igdb/image/upload/t_cover_big/co1fear.jpg"
    }


def test_igdb_steam_mapping_without_credentials_is_empty(db):
    from app.providers.igdb import covers_for_steam_appids

    assert covers_for_steam_appids(db, [21090]) == {}


@respx.mock
def test_igdb_release_dates_for_steam_appids(db, keys):
    keys(TWITCH_CLIENT_ID="cid", TWITCH_CLIENT_SECRET="sec")
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 9999})
    )
    respx.post("https://api.igdb.com/v4/external_games").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "uid": "367520", "game": {"id": 5, "first_release_date": 1487894400}},
                {"id": 2, "uid": "400", "game": {"id": 6}},  # no date known
            ],
        )
    )
    from app.providers.igdb import release_dates_for_steam_appids

    out = release_dates_for_steam_appids(db, [367520, 400])
    assert out == {367520: "2017-02-24"}


@respx.mock
def test_igdb_release_dates_for_igdb_ids(db, keys):
    keys(TWITCH_CLIENT_ID="cid", TWITCH_CLIENT_SECRET="sec")
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 9999})
    )
    respx.post("https://api.igdb.com/v4/games").mock(
        return_value=httpx.Response(
            200, json=[{"id": 119133, "first_release_date": 1645747200}]
        )
    )
    from app.providers.igdb import release_dates_for_igdb_ids

    out = release_dates_for_igdb_ids(db, [119133, 14593])
    assert out == {119133: "2022-02-25"}
