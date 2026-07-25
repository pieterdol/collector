"""Per-episode watch tracking for TV seasons.

Episodes are fetched from TMDB lazily — the first time a season is opened —
and cached both in provider_cache and as item_episodes rows. Watch state
syncs both ways with the season flag: the last episode ticked marks the
season watched, and marking the season watched ticks every episode.
"""

import httpx
import pytest
import respx
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import SessionLocal
from app.models import ItemEpisode, ItemSeason
from app.tests.helpers import auth_headers, create_item

SEASONS_META = [
    {"tmdb_season_id": 3627, "season_number": 1, "name": "Season 1",
     "episode_count": 3, "air_date": "2011-04-17", "poster_path": None},
    {"tmdb_season_id": 3625, "season_number": 2, "name": "Season 2",
     "episode_count": 2, "air_date": "2012-04-01", "poster_path": None},
]


def episode(number: int, **overrides) -> dict:
    payload = {
        "id": 63000 + number,
        "episode_number": number,
        "name": f"Episode {number}",
        "overview": f"Things happen in {number}.",
        "air_date": "2011-04-17",
        "runtime": 55,
    }
    payload.update(overrides)
    return payload


SEASON_ONE = {"id": 3627, "season_number": 1, "name": "Season 1",
              "episodes": [episode(1), episode(2), episode(3)]}


@pytest.fixture
def tmdb(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "k")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def tv_item(client, headers, **overrides):
    metadata = {"tmdb_id": 1399, "seasons": SEASONS_META}
    metadata.update(overrides.pop("metadata", {}))
    return create_item(
        client, headers, type="tv", title="Game of Thrones", metadata=metadata, **overrides
    )


def mock_season(payload=SEASON_ONE, tv_id=1399, number=1):
    return respx.get(f"https://api.themoviedb.org/3/tv/{tv_id}/season/{number}").mock(
        return_value=httpx.Response(200, json=payload)
    )


def refresh(client, headers, item_id, number=1):
    res = client.post(
        f"/api/items/{item_id}/seasons/{number}/episodes/refresh", headers=headers
    )
    assert res.status_code == 200, res.text
    return res.json()


def activity_types(client, headers, item_id) -> list[str]:
    res = client.get(f"/api/items/{item_id}/activity", headers=headers)
    assert res.status_code == 200, res.text
    return [e["event_type"] for e in res.json()["events"]]


# --- schema constraints -----------------------------------------------------


def test_item_episodes_rejects_duplicate_episode(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="tv", title="Show")
    with SessionLocal() as db:
        season = ItemSeason(item_id=item["id"], season_number=1)
        db.add(season)
        db.commit()
        db.add(ItemEpisode(season_id=season.id, episode_number=1))
        db.commit()
        db.add(ItemEpisode(season_id=season.id, episode_number=1))
        with pytest.raises(IntegrityError):
            db.commit()


def test_deleting_season_cascades_episodes(client, tmdb):
    headers = auth_headers(client)
    with respx.mock:
        mock_season()
        item = tv_item(client, headers)
        refresh(client, headers, item["id"])
    assert client.delete(
        f"/api/items/{item['id']}/seasons/1", headers=headers
    ).status_code == 204
    with SessionLocal() as db:
        assert db.query(ItemEpisode).count() == 0


def test_deleting_item_cascades_episodes(client, tmdb):
    headers = auth_headers(client)
    with respx.mock:
        mock_season()
        item = tv_item(client, headers)
        refresh(client, headers, item["id"])
    assert client.delete(f"/api/items/{item['id']}", headers=headers).status_code == 204
    with SessionLocal() as db:
        assert db.query(ItemEpisode).count() == 0


# --- refresh (lazy TMDB fetch) ----------------------------------------------


@respx.mock
def test_refresh_creates_episode_rows_from_tmdb(client, tmdb):
    headers = auth_headers(client)
    route = mock_season()
    item = tv_item(client, headers)

    body = refresh(client, headers, item["id"])
    assert route.called
    assert body["total"] == 3
    assert body["watched"] == 0
    first = body["episodes"][0]
    assert first["episode_number"] == 1
    assert first["name"] == "Episode 1"
    assert first["air_date"] == "2011-04-17"
    assert first["runtime"] == 55
    assert first["tmdb_episode_id"] == 63001
    assert first["watched"] is False
    assert [e["episode_number"] for e in body["episodes"]] == [1, 2, 3]


@respx.mock
def test_refresh_is_idempotent_and_keeps_watch_state(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])
    client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/2",
        json={"watched": True},
        headers=headers,
    )

    body = refresh(client, headers, item["id"])
    assert body["total"] == 3  # no duplicate rows
    assert body["watched"] == 1
    assert body["episodes"][1]["watched"] is True


@respx.mock
def test_refresh_adds_new_episodes_and_updates_season_count(client, tmdb):
    """Ongoing shows grow: a later refresh picks up the new episodes."""
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])

    # Season 1 reported 3 episodes at add time; TMDB now lists 4.
    respx.get("https://api.themoviedb.org/3/tv/1399/season/1").mock(
        return_value=httpx.Response(
            200,
            json={"id": 3627, "season_number": 1,
                  "episodes": [episode(1), episode(2), episode(3), episode(4)]},
        )
    )
    body = client.post(
        f"/api/items/{item['id']}/seasons/1/episodes/refresh?force=true", headers=headers
    ).json()
    assert body["total"] == 4

    seasons = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert seasons["seasons"][0]["episode_count"] == 4


@respx.mock
def test_refresh_rejects_show_without_tmdb_link(client, tmdb):
    headers = auth_headers(client)
    item = create_item(client, headers, type="tv", title="Home Movies", metadata={})
    client.patch(f"/api/items/{item['id']}/seasons/1", json={}, headers=headers)
    res = client.post(
        f"/api/items/{item['id']}/seasons/1/episodes/refresh", headers=headers
    )
    assert res.status_code == 400


def test_refresh_without_tmdb_key_returns_503(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    res = client.post(
        f"/api/items/{item['id']}/seasons/1/episodes/refresh", headers=headers
    )
    assert res.status_code == 503


@respx.mock
def test_refresh_rejects_non_tv_item(client, tmdb):
    headers = auth_headers(client)
    item = create_item(client, headers, type="movie", title="Arrival")
    res = client.post(
        f"/api/items/{item['id']}/seasons/1/episodes/refresh", headers=headers
    )
    assert res.status_code == 400


@respx.mock
def test_refresh_404_for_other_users_item(client, tmdb):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    other = auth_headers(client, email="other@example.com", name="Other")
    assert client.post(
        f"/api/items/{item['id']}/seasons/1/episodes/refresh", headers=other
    ).status_code == 404


# --- listing ----------------------------------------------------------------


@respx.mock
def test_list_episodes_is_empty_before_the_first_fetch(client, tmdb):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    res = client.get(f"/api/items/{item['id']}/seasons/1/episodes", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"episodes": [], "total": 0, "watched": 0}


@respx.mock
def test_list_episodes_reports_watched_aggregate(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])
    for number in (1, 2):
        client.patch(
            f"/api/items/{item['id']}/seasons/1/episodes/{number}",
            json={"watched": True},
            headers=headers,
        )

    body = client.get(f"/api/items/{item['id']}/seasons/1/episodes", headers=headers).json()
    assert (body["total"], body["watched"]) == (3, 2)


@respx.mock
def test_season_list_carries_episode_counts(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])
    client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/1",
        json={"watched": True},
        headers=headers,
    )

    seasons = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    one, two = seasons["seasons"]
    assert (one["episodes_tracked"], one["episodes_watched"]) == (3, 1)
    assert (two["episodes_tracked"], two["episodes_watched"]) == (0, 0)


def test_list_episodes_404_for_other_users_item(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    other = auth_headers(client, email="other@example.com", name="Other")
    assert client.get(
        f"/api/items/{item['id']}/seasons/1/episodes", headers=other
    ).status_code == 404


# --- per-episode watch state ------------------------------------------------


@respx.mock
def test_patch_episode_watched_records_event(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])

    res = client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/2",
        json={"watched": True},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["watched"] is True

    events = client.get(f"/api/items/{item['id']}/activity", headers=headers).json()["events"]
    watched = next(e for e in events if e["event_type"] == "episode_watched")
    assert watched["new_value"] == {"season_number": 1, "episode_number": 2, "watched": True}
    assert watched["old_value"] == {"season_number": 1, "episode_number": 2, "watched": False}


@respx.mock
def test_patch_episode_noop_writes_no_event(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])

    client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/1",
        json={"watched": False},
        headers=headers,
    )
    assert "episode_watched" not in activity_types(client, headers, item["id"])


@respx.mock
def test_patch_episode_404_when_not_tracked(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])
    res = client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/99",
        json={"watched": True},
        headers=headers,
    )
    assert res.status_code == 404


def test_patch_episode_404_for_other_users_item(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    other = auth_headers(client, email="other@example.com", name="Other")
    assert client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/1",
        json={"watched": True},
        headers=other,
    ).status_code == 404


# --- two-way sync with the season flag --------------------------------------


@respx.mock
def test_watching_the_last_episode_marks_the_season_watched(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])

    for number in (1, 2):
        client.patch(
            f"/api/items/{item['id']}/seasons/1/episodes/{number}",
            json={"watched": True},
            headers=headers,
        )
    seasons = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert seasons["seasons"][0]["watched"] is False  # not there yet

    client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/3",
        json={"watched": True},
        headers=headers,
    )
    seasons = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert seasons["seasons"][0]["watched"] is True
    assert seasons["watched_seasons"] == 1
    # The derived flip is a season state change, so it is logged as one.
    assert "season_watched" in activity_types(client, headers, item["id"])


@respx.mock
def test_unwatching_one_episode_clears_the_season_flag(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])
    client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=headers
    )

    client.patch(
        f"/api/items/{item['id']}/seasons/1/episodes/2",
        json={"watched": False},
        headers=headers,
    )
    seasons = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert seasons["seasons"][0]["watched"] is False
    assert seasons["seasons"][0]["episodes_watched"] == 2


@respx.mock
def test_marking_the_season_watched_ticks_every_episode(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])

    res = client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=headers
    )
    assert res.status_code == 200
    body = client.get(f"/api/items/{item['id']}/seasons/1/episodes", headers=headers).json()
    assert body["watched"] == 3
    assert all(e["watched"] for e in body["episodes"])


@respx.mock
def test_bulk_season_mark_logs_one_event_not_one_per_episode(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])

    client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=headers
    )
    types = activity_types(client, headers, item["id"])
    assert types.count("season_watched") == 1
    assert "episode_watched" not in types


@respx.mock
def test_marking_the_season_unwatched_clears_every_episode(client, tmdb):
    headers = auth_headers(client)
    mock_season()
    item = tv_item(client, headers)
    refresh(client, headers, item["id"])
    client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=headers
    )

    client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": False}, headers=headers
    )
    body = client.get(f"/api/items/{item['id']}/seasons/1/episodes", headers=headers).json()
    assert body["watched"] == 0


@respx.mock
def test_season_without_episodes_keeps_its_manual_flag(client, tmdb):
    """Shows nobody has fetched episodes for still toggle at season level."""
    headers = auth_headers(client)
    item = tv_item(client, headers)
    res = client.patch(
        f"/api/items/{item['id']}/seasons/2", json={"watched": True}, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["watched"] is True
