"""Per-season ownership and watch tracking for TV shows."""

import httpx
import pytest
import respx
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import ItemSeason
from app.tests.helpers import auth_headers, create_item

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c626001000000ffff03000006000557"
    "bfabd40000000049454e44ae426082"
)


def png_response(*_args, **_kwargs):
    return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})


# Shaped like TmdbProvider.details() output for a TV show (see TMDB-tv.json).
SEASONS_META = [
    {"tmdb_season_id": 3624, "season_number": 0, "name": "Specials",
     "episode_count": 14, "air_date": "2010-12-05", "poster_path": None},
    {"tmdb_season_id": 3627, "season_number": 1, "name": "Season 1",
     "episode_count": 10, "air_date": "2011-04-17", "poster_path": None},
    {"tmdb_season_id": 3625, "season_number": 2, "name": "Season 2",
     "episode_count": 10, "air_date": "2012-04-01", "poster_path": None},
]


def tv_item(client, headers, seasons=SEASONS_META, **overrides):
    metadata = {"tmdb_id": 1399}
    if seasons is not None:
        metadata["seasons"] = seasons
    return create_item(
        client, headers, type="tv", title="Game of Thrones",
        metadata=metadata, **overrides,
    )


# --- schema constraints -----------------------------------------------------


def test_item_seasons_rejects_invalid_media(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="tv", title="Show")
    with SessionLocal() as db:
        db.add(ItemSeason(item_id=item["id"], season_number=1, media="Betamax"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_item_seasons_rejects_duplicate_season(client):
    headers = auth_headers(client)
    item = create_item(client, headers, type="tv", title="Show")
    with SessionLocal() as db:
        db.add(ItemSeason(item_id=item["id"], season_number=1))
        db.commit()
        db.add(ItemSeason(item_id=item["id"], season_number=1))
        with pytest.raises(IntegrityError):
            db.commit()


def test_deleting_item_cascades_seasons(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    assert client.delete(f"/api/items/{item['id']}", headers=headers).status_code == 204
    with SessionLocal() as db:
        assert db.query(ItemSeason).filter_by(item_id=item["id"]).count() == 0


# --- season rows from provider metadata at create time ----------------------


@respx.mock
def test_tv_create_builds_season_rows_from_metadata(client):
    respx.get(url__regex=r"https://image\.tmdb\.org/t/p/w300/.*").mock(
        side_effect=png_response
    )
    headers = auth_headers(client)
    seasons = [dict(s) for s in SEASONS_META]
    seasons[1]["poster_path"] = "/s1.jpg"
    item = tv_item(client, headers, seasons=seasons)

    # rows are the single source of truth — the metadata list is dropped
    assert "seasons" not in item["metadata"]

    body = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert [s["season_number"] for s in body["seasons"]] == [0, 1, 2]
    s1 = body["seasons"][1]
    assert s1["name"] == "Season 1"
    assert s1["episode_count"] == 10
    assert s1["air_date"] == "2011-04-17"
    assert s1["watched"] is False
    assert s1["ownership"] is None
    assert s1["poster_path"] == f"/media/seasons/{item['id']}/s1.png"
    assert body["seasons"][2]["poster_path"] is None
    assert body["total_seasons"] == 2  # Specials don't count


def test_tv_create_without_seasons_metadata_creates_no_rows(client):
    headers = auth_headers(client)
    item = tv_item(client, headers, seasons=None)
    body = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert body["seasons"] == []
    assert body["total_seasons"] == 0


@respx.mock
def test_season_poster_failure_does_not_block_create(client):
    respx.get(url__regex=r"https://image\.tmdb\.org/t/p/w300/.*").mock(
        return_value=httpx.Response(500)
    )
    headers = auth_headers(client)
    seasons = [dict(s, poster_path=f"/s{s['season_number']}.jpg") for s in SEASONS_META]
    item = tv_item(client, headers, seasons=seasons)
    body = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert len(body["seasons"]) == 3
    assert all(s["poster_path"] is None for s in body["seasons"])


# --- GET aggregates ----------------------------------------------------------


def test_get_seasons_reports_watched_aggregates(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    client.patch(f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=headers)
    client.patch(f"/api/items/{item['id']}/seasons/0", json={"watched": True}, headers=headers)
    body = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert body["total_seasons"] == 2
    assert body["watched_seasons"] == 1  # Specials excluded from progress
    assert body["owned_seasons"] == 0


# --- PATCH: upsert + activity events -----------------------------------------


def activity_types(client, headers, item_id) -> list[str]:
    events = client.get(f"/api/items/{item_id}/activity", headers=headers).json()["events"]
    return [e["event_type"] for e in events]


def test_patch_season_watched_records_event(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    res = client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["watched"] is True

    events = client.get(f"/api/items/{item['id']}/activity", headers=headers).json()["events"]
    watched = [e for e in events if e["event_type"] == "season_watched"]
    assert len(watched) == 1
    assert watched[0]["new_value"] == {"season_number": 1, "watched": True}

    client.patch(f"/api/items/{item['id']}/seasons/1", json={"watched": False}, headers=headers)
    assert activity_types(client, headers, item["id"]).count("season_watched") == 2


def test_patch_season_ownership_records_season_acquired(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    res = client.patch(
        f"/api/items/{item['id']}/seasons/1",
        json={"ownership": "owned", "format": "physical", "media": "Blu-ray"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    season = res.json()
    assert season["ownership"] == "owned"
    assert season["format"] == "physical"
    assert season["media"] == "Blu-ray"

    events = client.get(f"/api/items/{item['id']}/activity", headers=headers).json()["events"]
    acquired = [e for e in events if e["event_type"] == "season_acquired"]
    assert len(acquired) == 1
    assert acquired[0]["new_value"]["season_number"] == 1
    assert acquired[0]["new_value"]["format"] == "physical"
    assert acquired[0]["new_value"]["media"] == "Blu-ray"
    # format/media ride the acquire event — no extra season_updated row
    assert "season_updated" not in activity_types(client, headers, item["id"])


def test_patch_season_media_change_records_season_updated(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    client.patch(
        f"/api/items/{item['id']}/seasons/2",
        json={"ownership": "owned", "format": "physical", "media": "Blu-ray"},
        headers=headers,
    )
    client.patch(f"/api/items/{item['id']}/seasons/2", json={"media": "DVD"}, headers=headers)

    events = client.get(f"/api/items/{item['id']}/activity", headers=headers).json()["events"]
    updated = [e for e in events if e["event_type"] == "season_updated"]
    assert len(updated) == 1
    assert updated[0]["old_value"]["media"] == "Blu-ray"
    assert updated[0]["new_value"] == {"season_number": 2, "media": "DVD"}


def test_patch_season_noop_writes_no_event(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    before = activity_types(client, headers, item["id"])
    client.patch(f"/api/items/{item['id']}/seasons/1", json={"watched": False}, headers=headers)
    assert activity_types(client, headers, item["id"]) == before


def test_patch_season_upserts_missing_row(client):
    headers = auth_headers(client)
    item = tv_item(client, headers, seasons=None)  # manual entry: no rows yet
    res = client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=headers
    )
    assert res.status_code == 200, res.text
    body = client.get(f"/api/items/{item['id']}/seasons", headers=headers).json()
    assert [s["season_number"] for s in body["seasons"]] == [1]
    assert body["watched_seasons"] == 1


def test_patch_season_rejects_invalid_media(client):
    headers = auth_headers(client)
    item = tv_item(client, headers)
    res = client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"media": "Betamax"}, headers=headers
    )
    assert res.status_code == 422


def test_patch_season_rejects_non_tv_item(client):
    headers = auth_headers(client)
    book = create_item(client, headers, type="book", title="Dune")
    res = client.patch(
        f"/api/items/{book['id']}/seasons/1", json={"watched": True}, headers=headers
    )
    assert res.status_code == 400


def test_seasons_404_for_other_users_item(client):
    mine = auth_headers(client, email="mine@example.com")
    other = auth_headers(client, email="other@example.com")
    item = tv_item(client, mine)
    assert client.get(f"/api/items/{item['id']}/seasons", headers=other).status_code == 404
    res = client.patch(
        f"/api/items/{item['id']}/seasons/1", json={"watched": True}, headers=other
    )
    assert res.status_code == 404


# --- shelf media filter -------------------------------------------------------


def test_media_filter_matches_season_media(client):
    headers = auth_headers(client)
    show = tv_item(client, headers)
    create_item(client, headers, type="movie", title="Some DVD", format="physical",
                metadata={"media": "DVD"})
    client.patch(
        f"/api/items/{show['id']}/seasons/1",
        json={"ownership": "owned", "format": "physical", "media": "Blu-ray"},
        headers=headers,
    )
    items = client.get("/api/items?media=Blu-ray", headers=headers).json()["items"]
    assert [i["title"] for i in items] == ["Game of Thrones"]
