import httpx
import respx

from app.tests.helpers import auth_headers
from app.tests.test_providers import OPENLIB_SEARCH


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


def test_barcode_upc_is_captured_but_unmatched(client):
    headers = auth_headers(client)
    res = client.get("/api/enrich/barcode?code=883929247318", headers=headers)
    body = res.json()
    assert body["matched"] is False
    assert body["kind"] == "upc"
    assert body["code"] == "883929247318"


def test_providers_status_lists_all(client):
    headers = auth_headers(client)
    res = client.get("/api/enrich/providers", headers=headers)
    body = {p["type"]: p for p in res.json()["providers"]}
    assert body["book"]["available"] is True  # Open Library needs no key
    assert body["movie"]["available"] is False
    assert body["game"]["available"] is False
