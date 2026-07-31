"""Bundling: several copies of the same thing under one library entry.

A bundle groups items that are the same release owned more than once (a game
on PS5 and PC, a movie on DVD and Blu-ray). Each copy stays its own item —
own platform, media, status, progress — but the library grid shows only one
of them, the "front" copy.
"""

import uuid

from app.tests.helpers import auth_headers, create_item


def game(client, headers, title, platform, **overrides) -> dict:
    return create_item(
        client,
        headers,
        type="game",
        title=title,
        metadata={"platform": platform},
        **overrides,
    )


def bundle(client, headers, item, others, expect=200):
    res = client.post(
        f"/api/items/{item['id']}/bundle",
        json={"item_ids": [o["id"] for o in others]},
        headers=headers,
    )
    assert res.status_code == expect, res.text
    return res.json() if res.status_code == 200 else res


def copies(client, headers, item) -> list[dict]:
    res = client.get(f"/api/items/{item['id']}/copies", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["copies"]


def listed(client, headers, query="") -> dict:
    res = client.get(f"/api/items{query}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_bundling_collapses_the_copies_into_one_library_entry(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")

    bundle(client, headers, ps5, [pc])

    body = listed(client, headers, "?type=game")
    assert body["total"] == 1
    assert [i["id"] for i in body["items"]] == [ps5["id"]]
    entry = body["items"][0]
    assert entry["bundle_count"] == 2
    assert entry["bundle_labels"] == ["PlayStation 5", "PC (Microsoft Windows)"]
    assert entry["bundle_id"] is not None
    assert entry["bundle_front"] is True


def test_an_unbundled_item_carries_no_bundle_fields(client):
    headers = auth_headers(client)
    solo = game(client, headers, "Hades", "PC (Microsoft Windows)")
    entry = listed(client, headers, "?type=game")["items"][0]
    assert entry["bundle_id"] is None
    assert entry["bundle_count"] == 1
    assert entry["bundle_labels"] == []
    assert copies(client, headers, solo) == []


def test_the_copy_you_bundled_from_fronts_the_bundle(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, pc, [ps5])  # bundled from the PC copy

    assert [i["id"] for i in listed(client, headers, "?type=game")["items"]] == [pc["id"]]
    front, second = copies(client, headers, ps5)
    assert (front["id"], front["bundle_front"]) == (pc["id"], True)
    assert (second["id"], second["bundle_front"]) == (ps5["id"], False)


def test_a_filter_shows_the_copy_that_matches_it(client):
    """Filtering on PC has to surface the PC copy, not the bundle's front."""
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])

    body = listed(client, headers, "?platform=PC+%28Microsoft+Windows%29")
    assert [i["id"] for i in body["items"]] == [pc["id"]]
    assert body["total"] == 1
    # The badge still counts the whole bundle, not just what matched.
    assert body["items"][0]["bundle_count"] == 2


def test_a_wishlisted_upgrade_bundles_with_the_copy_you_own(client):
    headers = auth_headers(client)
    dvd = create_item(
        client, headers, type="movie", title="Heat", format="physical",
        metadata={"media": "DVD"},
    )
    bluray = create_item(
        client, headers, type="movie", title="Heat", status="wishlist",
        metadata={"media": "Blu-ray"},
    )
    bundle(client, headers, dvd, [bluray])

    library = listed(client, headers, "?status=backlog")
    assert [i["id"] for i in library["items"]] == [dvd["id"]]
    wishlist = listed(client, headers, "?status=wishlist")
    assert [i["id"] for i in wishlist["items"]] == [bluray["id"]]
    assert wishlist["items"][0]["bundle_count"] == 2
    assert library["items"][0]["bundle_labels"] == ["DVD", "Blu-ray"]


def test_searching_still_returns_one_row_per_bundle(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])

    body = listed(client, headers, "?q=elden")
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_choosing_which_copy_the_library_shows(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])

    res = client.post(f"/api/items/{pc['id']}/bundle/front", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["bundle_front"] is True

    assert [i["id"] for i in listed(client, headers, "?type=game")["items"]] == [pc["id"]]
    assert [c["id"] for c in copies(client, headers, ps5)] == [pc["id"], ps5["id"]]


def test_fronting_an_unbundled_item_is_rejected(client):
    headers = auth_headers(client)
    solo = game(client, headers, "Hades", "PC (Microsoft Windows)")
    res = client.post(f"/api/items/{solo['id']}/bundle/front", headers=headers)
    assert res.status_code == 400


def test_unbundling_a_copy_leaves_the_rest_together(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    ps4 = game(client, headers, "Elden Ring", "PlayStation 4")
    bundle(client, headers, ps5, [pc, ps4])

    res = client.delete(f"/api/items/{ps4['id']}/bundle", headers=headers)
    assert res.status_code == 204, res.text

    body = listed(client, headers, "?type=game")
    assert body["total"] == 2
    assert [i["id"] for i in body["items"]] == [ps4["id"], ps5["id"]]  # newest first
    assert copies(client, headers, ps4) == []
    assert len(copies(client, headers, ps5)) == 2


def test_a_two_copy_bundle_dissolves_when_one_leaves(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])

    client.delete(f"/api/items/{pc['id']}/bundle", headers=headers)

    body = listed(client, headers, "?type=game")
    assert body["total"] == 2
    for entry in body["items"]:
        assert entry["bundle_id"] is None
        assert entry["bundle_front"] is False
        assert entry["bundle_count"] == 1


def test_unbundling_the_front_copy_promotes_the_oldest_remaining(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    ps4 = game(client, headers, "Elden Ring", "PlayStation 4")
    bundle(client, headers, ps5, [pc, ps4])

    client.delete(f"/api/items/{ps5['id']}/bundle", headers=headers)

    remaining = copies(client, headers, pc)
    assert [c["id"] for c in remaining] == [pc["id"], ps4["id"]]
    assert remaining[0]["bundle_front"] is True


def test_unbundling_an_unbundled_item_is_rejected(client):
    headers = auth_headers(client)
    solo = game(client, headers, "Hades", "PC (Microsoft Windows)")
    assert client.delete(f"/api/items/{solo['id']}/bundle", headers=headers).status_code == 400


def test_bundling_with_a_bundled_copy_merges_both_bundles(client):
    headers = auth_headers(client)
    a = game(client, headers, "Elden Ring", "PlayStation 5")
    b = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    c = game(client, headers, "Elden Ring", "PlayStation 4")
    d = game(client, headers, "Elden Ring", "Xbox One")
    bundle(client, headers, a, [b])
    bundle(client, headers, c, [d])

    bundle(client, headers, a, [c])

    members = copies(client, headers, d)
    assert len(members) == 4
    assert [m["bundle_front"] for m in members] == [True, False, False, False]
    assert members[0]["id"] == a["id"]
    assert len({m["bundle_id"] for m in members}) == 1
    assert listed(client, headers, "?type=game")["total"] == 1


def test_bundling_an_item_already_in_the_bundle_changes_nothing(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])
    bundle(client, headers, ps5, [pc])

    assert len(copies(client, headers, ps5)) == 2
    events = client.get(f"/api/items/{pc['id']}/activity", headers=headers).json()["events"]
    assert [e["event_type"] for e in events].count("bundled") == 1


def test_only_copies_of_the_same_type_can_be_bundled(client):
    headers = auth_headers(client)
    movie = create_item(client, headers, type="movie", title="Dune")
    book = create_item(client, headers, type="book", title="Dune")
    res = bundle(client, headers, movie, [book], expect=400)
    assert "same type" in res.json()["detail"].lower()


def test_bundling_needs_something_to_bundle_with(client):
    headers = auth_headers(client)
    solo = game(client, headers, "Hades", "PC (Microsoft Windows)")
    res = client.post(f"/api/items/{solo['id']}/bundle", json={"item_ids": []}, headers=headers)
    assert res.status_code == 422


def test_bundling_an_item_with_itself_is_rejected(client):
    headers = auth_headers(client)
    solo = game(client, headers, "Hades", "PC (Microsoft Windows)")
    res = bundle(client, headers, solo, [solo], expect=400)
    assert res.status_code == 400
    assert copies(client, headers, solo) == []


def test_someone_elses_copy_cannot_be_bundled_in(client):
    headers = auth_headers(client)
    other = auth_headers(client, email="other@example.com", name="Other")
    mine = game(client, headers, "Elden Ring", "PlayStation 5")
    theirs = game(client, other, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, mine, [theirs], expect=404)
    assert copies(client, headers, mine) == []


def test_bundling_an_unknown_item_is_a_404(client):
    headers = auth_headers(client)
    mine = game(client, headers, "Elden Ring", "PlayStation 5")
    res = client.post(
        f"/api/items/{mine['id']}/bundle",
        json={"item_ids": [str(uuid.uuid4())]},
        headers=headers,
    )
    assert res.status_code == 404


def test_bundling_and_unbundling_are_logged(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])

    def types(item):
        res = client.get(f"/api/items/{item['id']}/activity", headers=headers)
        return [e["event_type"] for e in res.json()["events"]]

    # Both copies changed, so both carry the event.
    assert types(ps5)[0] == "bundled"
    assert types(pc)[0] == "bundled"
    joined = client.get(f"/api/items/{pc['id']}/activity", headers=headers).json()["events"][0]
    assert joined["new_value"]["with"] == "Elden Ring"

    client.post(f"/api/items/{pc['id']}/bundle/front", headers=headers)
    assert types(pc)[0] == "bundle_front"
    assert types(ps5)[0] == "bundle_front"

    client.delete(f"/api/items/{pc['id']}/bundle", headers=headers)
    assert types(pc)[0] == "unbundled"
    assert types(ps5)[0] == "unbundled"  # the bundle dissolved under it


def test_deleting_the_front_copy_keeps_the_bundle_usable(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    ps4 = game(client, headers, "Elden Ring", "PlayStation 4")
    bundle(client, headers, ps5, [pc, ps4])

    assert client.delete(f"/api/items/{ps5['id']}", headers=headers).status_code == 204

    body = listed(client, headers, "?type=game")
    assert body["total"] == 1
    entry = body["items"][0]
    assert entry["id"] == pc["id"]
    assert entry["bundle_front"] is True
    assert entry["bundle_count"] == 2


def test_deleting_down_to_one_copy_dissolves_the_bundle(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])

    client.delete(f"/api/items/{pc['id']}", headers=headers)

    entry = listed(client, headers, "?type=game")["items"][0]
    assert entry["id"] == ps5["id"]
    assert entry["bundle_id"] is None
    assert entry["bundle_front"] is False


def test_a_single_item_fetch_reports_its_bundle(client):
    headers = auth_headers(client)
    ps5 = game(client, headers, "Elden Ring", "PlayStation 5")
    pc = game(client, headers, "Elden Ring", "PC (Microsoft Windows)")
    bundle(client, headers, ps5, [pc])

    body = client.get(f"/api/items/{pc['id']}", headers=headers).json()
    assert body["bundle_count"] == 2
    assert body["bundle_front"] is False
    assert body["bundle_id"] is not None
