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
