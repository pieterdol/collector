from app.tests.helpers import auth_headers, create_item


def seed_collection(client, headers):
    create_item(client, headers, type="book", title="Dune", status="in_progress")
    create_item(client, headers, type="book", title="Project Hail Mary", status="completed")
    create_item(client, headers, type="movie", title="Blade Runner 2049", status="completed")
    create_item(
        client, headers, type="game", title="Hollow Knight", status="backlog", format="digital"
    )


def titles(res) -> list[str]:
    return [i["title"] for i in res.json()["items"]]


def test_filter_by_type(client):
    headers = auth_headers(client)
    seed_collection(client, headers)
    res = client.get("/api/items?type=book", headers=headers)
    assert sorted(titles(res)) == ["Dune", "Project Hail Mary"]


def test_filter_by_status_and_format(client):
    headers = auth_headers(client)
    seed_collection(client, headers)
    assert titles(client.get("/api/items?status=completed&type=movie", headers=headers)) == [
        "Blade Runner 2049"
    ]
    assert titles(client.get("/api/items?format=digital", headers=headers)) == ["Hollow Knight"]


def test_multi_value_filters(client):
    headers = auth_headers(client)
    seed_collection(client, headers)
    res = client.get("/api/items?type=book&type=game", headers=headers)
    assert len(titles(res)) == 3


def test_full_text_search_matches_partial_words(client):
    headers = auth_headers(client)
    seed_collection(client, headers)
    assert titles(client.get("/api/items?q=hail", headers=headers)) == ["Project Hail Mary"]
    assert titles(client.get("/api/items?q=runner", headers=headers)) == ["Blade Runner 2049"]
    # prefix typing should already match
    assert titles(client.get("/api/items?q=holl", headers=headers)) == ["Hollow Knight"]


def test_sort_title_asc(client):
    headers = auth_headers(client)
    seed_collection(client, headers)
    res = client.get("/api/items?sort=title", headers=headers)
    assert titles(res) == sorted(titles(res))


def test_default_sort_is_newest_first(client):
    headers = auth_headers(client)
    seed_collection(client, headers)
    assert titles(client.get("/api/items", headers=headers))[0] == "Hollow Knight"


def test_pagination_returns_total(client):
    headers = auth_headers(client)
    seed_collection(client, headers)
    res = client.get("/api/items?limit=2&offset=0", headers=headers)
    body = res.json()
    assert body["total"] == 4
    assert len(body["items"]) == 2
    res2 = client.get("/api/items?limit=2&offset=2", headers=headers)
    assert len(res2.json()["items"]) == 2
    assert {i["id"] for i in body["items"]}.isdisjoint(
        {i["id"] for i in res2.json()["items"]}
    )


def test_filter_by_platform(client):
    headers = auth_headers(client)
    create_item(client, headers, type="game", title="Zelda", format="physical",
                metadata={"platform": "Nintendo Switch"})
    create_item(client, headers, type="game", title="Wolfenstein", format="physical",
                metadata={"platform": "Xbox One"})
    create_item(client, headers, type="game", title="Steam Thing", format="digital",
                metadata={"platform": "PC (Steam)"})
    res = client.get("/api/items?platform=Nintendo Switch", headers=headers)
    assert titles(res) == ["Zelda"]


def test_platforms_endpoint_lists_distinct_owned_platforms(client):
    headers = auth_headers(client)
    create_item(client, headers, type="game", title="A", metadata={"platform": "Xbox One"})
    create_item(client, headers, type="game", title="B", metadata={"platform": "Xbox One"})
    create_item(client, headers, type="game", title="C", metadata={"platform": "Nintendo Switch"})
    create_item(client, headers, type="book", title="No Platform")
    other = auth_headers(client, email="someone@else.com")
    create_item(client, other, type="game", title="X", metadata={"platform": "PS Vita"})

    res = client.get("/api/items/platforms", headers=headers)
    assert res.status_code == 200
    assert res.json()["platforms"] == ["Nintendo Switch", "Xbox One"]


def test_filter_movies_by_media(client):
    headers = auth_headers(client)
    create_item(
        client, headers, type="movie", title="Heat", metadata={"media": "Blu-ray"}
    )
    create_item(
        client, headers, type="movie", title="Alien", metadata={"media": "Ultra HD Blu-ray"}
    )
    create_item(client, headers, type="movie", title="Se7en", metadata={})

    assert titles(client.get("/api/items?media=Blu-ray", headers=headers)) == ["Heat"]
    assert titles(
        client.get("/api/items?media=Ultra+HD+Blu-ray", headers=headers)
    ) == ["Alien"]
    assert titles(client.get("/api/items?media=DVD", headers=headers)) == []


def test_pagination_is_stable_when_created_at_ties(client):
    """Steam imports batch-create items with identical created_at; offset
    pages must still be disjoint and cover everything (stable tiebreaker).

    The heap is shuffled after the timestamp update so ties have no
    accidental physical order to fall back on."""
    import random

    from sqlalchemy import text

    from app.db import SessionLocal

    headers = auth_headers(client)
    expected = {f"Tied game {i:02d}" for i in range(60)}
    for title in expected:
        create_item(client, headers, type="game", title=title, format="digital")

    session = SessionLocal()
    session.execute(text("UPDATE items SET created_at = '2026-07-01 12:00:00+00'"))
    shuffled = list(expected)
    random.shuffle(shuffled)
    for title in shuffled:  # individual updates scatter heap order
        session.execute(text("UPDATE items SET review = 'x' WHERE title = :t"), {"t": title})
    session.commit()
    session.close()

    seen: list[str] = []
    for offset in range(0, 63, 7):
        res = client.get(f"/api/items?limit=7&offset={offset}", headers=headers)
        seen.extend(titles(res))
    assert len(seen) == len(set(seen)), f"pages overlap: {sorted(set(t for t in seen if seen.count(t) > 1))}"
    assert set(seen) == expected


def seed_batman(client, headers):
    """A title match, two description-only matches, and a non-match."""
    create_item(client, headers, type="movie", title="Batman Begins", status="completed")
    create_item(
        client, headers, type="movie", title="The Dark Knight", status="completed",
        # TMDB stores the synopsis as `overview`; artwork enrichment writes
        # `description` for games.
        metadata={"overview": "Batman raises the stakes in his war on crime."},
    )
    create_item(
        client, headers, type="game", title="Gotham Knights", status="backlog",
        metadata={"description": "Batman is dead. Step into the Batfamily's shoes."},
    )
    create_item(client, headers, type="book", title="Dune", status="backlog")


def test_search_matches_descriptions_after_titles(client):
    headers = auth_headers(client)
    seed_batman(client, headers)

    found = titles(client.get("/api/items?q=batman", headers=headers))
    # Title match ranks first; description-only matches follow.
    assert found[0] == "Batman Begins"
    assert set(found[1:]) == {"The Dark Knight", "Gotham Knights"}
    assert "Dune" not in found


def test_search_ranking_survives_an_explicit_sort(client):
    headers = auth_headers(client)
    seed_batman(client, headers)

    found = titles(client.get("/api/items?q=batman&sort=title", headers=headers))
    assert found[0] == "Batman Begins"  # still the title tier
    assert found[1:] == ["Gotham Knights", "The Dark Knight"]  # A→Z within tier


def test_description_search_respects_other_filters(client):
    headers = auth_headers(client)
    seed_batman(client, headers)

    assert titles(client.get("/api/items?q=batman&type=game", headers=headers)) == [
        "Gotham Knights"
    ]


def test_search_still_ignores_unrelated_metadata_text(client):
    headers = auth_headers(client)
    create_item(
        client, headers, type="game", title="Some Game",
        metadata={"storefront": "Batman Store", "platform": "PC (Microsoft Windows)"},
    )
    # Only human-readable synopsis fields are searched, not bookkeeping.
    assert titles(client.get("/api/items?q=batman", headers=headers)) == []
