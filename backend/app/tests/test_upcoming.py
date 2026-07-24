"""Upcoming filter: items with a future (or still-running partial)
release_date, across library and wishlist, sorted soonest-first."""

from datetime import date, timedelta

from app.tests.helpers import auth_headers, create_item


def iso(days_from_now: int) -> str:
    return (date.today() + timedelta(days=days_from_now)).isoformat()


def titles(res) -> list[str]:
    assert res.status_code == 200, res.text
    return [i["title"] for i in res.json()["items"]]


def with_release(client, headers, title, release, **overrides):
    meta = {"release_date": release} if release is not None else {}
    return create_item(client, headers, title=title, metadata=meta, **overrides)


def test_upcoming_keeps_future_and_running_partial_dates(client):
    headers = auth_headers(client)
    today = date.today()
    with_release(client, headers, "Tomorrow", iso(1))
    with_release(client, headers, "Today", iso(0))
    with_release(client, headers, "Yesterday", iso(-1))
    with_release(client, headers, "This year", str(today.year))
    with_release(client, headers, "Last year", str(today.year - 1))
    with_release(client, headers, "This month", f"{today.year}-{today.month:02d}")
    with_release(client, headers, "No release", None)

    res = client.get("/api/items?upcoming=true", headers=headers)
    assert sorted(titles(res)) == ["This month", "This year", "Today", "Tomorrow"]


def test_upcoming_spans_wishlist_and_library(client):
    headers = auth_headers(client)
    with_release(client, headers, "Preordered game", iso(3), type="game", status="backlog")
    with_release(client, headers, "Wished movie", iso(5), type="movie", status="wishlist")

    res = client.get("/api/items?upcoming=true", headers=headers)
    assert sorted(titles(res)) == ["Preordered game", "Wished movie"]


def test_upcoming_combines_with_type_filter(client):
    headers = auth_headers(client)
    with_release(client, headers, "Game soon", iso(2), type="game")
    with_release(client, headers, "Book soon", iso(2), type="book")

    res = client.get("/api/items?upcoming=true&type=game", headers=headers)
    assert titles(res) == ["Game soon"]


def test_sort_release_orders_soonest_first_with_partials_at_period_start(client):
    headers = auth_headers(client)
    next_year = date.today().year + 1
    with_release(client, headers, "Mid next year", f"{next_year}-06-15")
    with_release(client, headers, "Sometime next year", str(next_year))
    with_release(client, headers, "Soon", iso(2))
    with_release(client, headers, "June next year", f"{next_year}-06")

    res = client.get("/api/items?upcoming=true&sort=release", headers=headers)
    assert titles(res) == ["Soon", "Sometime next year", "June next year", "Mid next year"]
