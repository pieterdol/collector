"""Open Library — books. No API key required.

Docs: https://openlibrary.org/dev/docs/api/search
      https://openlibrary.org/dev/docs/api/books
"""

import httpx

from app.domain.enums import ItemType
from app.providers.base import MetadataProvider, MetadataResult
from app.providers.cache import cached_fetch

SEARCH_URL = "https://openlibrary.org/search.json"
BOOKS_URL = "https://openlibrary.org/api/books"
COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
# Covers are often available by ISBN even when the edition record lacks a
# cover link; default=false makes missing covers a 404 instead of a pixel.
ISBN_COVER_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"


class OpenLibraryProvider(MetadataProvider):
    name = "openlibrary"
    item_type = ItemType.BOOK

    def search(self, query: str) -> list[MetadataResult]:
        def fetch() -> dict:
            res = httpx.get(
                SEARCH_URL,
                params={
                    "q": query,
                    "limit": 10,
                    "fields": "title,author_name,first_publish_year,"
                    "number_of_pages_median,publisher,isbn,cover_i",
                },
                timeout=10,
            )
            res.raise_for_status()
            return res.json()

        try:
            data = cached_fetch(self.db, self.name, f"search:{query.lower()}", fetch)
        except httpx.HTTPError:
            return []
        return [self._map_doc(doc) for doc in data.get("docs", [])]

    def lookup_barcode(self, code: str) -> MetadataResult | None:
        def fetch() -> dict:
            res = httpx.get(
                BOOKS_URL,
                params={"bibkeys": f"ISBN:{code}", "format": "json", "jscmd": "data"},
                timeout=10,
            )
            res.raise_for_status()
            return res.json()

        try:
            data = cached_fetch(self.db, self.name, f"isbn:{code}", fetch)
        except httpx.HTTPError:
            return None
        entry = data.get(f"ISBN:{code}")
        if not entry:
            return None
        return MetadataResult(
            title=entry.get("title", "Unknown"),
            item_type=ItemType.BOOK,
            metadata={
                "authors": [a["name"] for a in entry.get("authors", [])],
                "isbn": code,
                "page_count": entry.get("number_of_pages"),
                "publisher": (entry.get("publishers") or [{}])[0].get("name"),
                "year": _year_from(entry.get("publish_date")),
            },
            cover_url=(entry.get("cover") or {}).get("large")
            or ISBN_COVER_URL.format(isbn=code),
            external_id=code,
        )

    def _map_doc(self, doc: dict) -> MetadataResult:
        isbn = (doc.get("isbn") or [None])[0]
        cover_id = doc.get("cover_i")
        return MetadataResult(
            title=doc.get("title", "Unknown"),
            item_type=ItemType.BOOK,
            metadata={
                "authors": doc.get("author_name", []),
                "isbn": isbn,
                "page_count": doc.get("number_of_pages_median"),
                "publisher": (doc.get("publisher") or [None])[0],
                "year": doc.get("first_publish_year"),
            },
            cover_url=COVER_URL.format(cover_id=cover_id) if cover_id else None,
            external_id=isbn,
        )


def _year_from(publish_date: str | None) -> int | None:
    if not publish_date:
        return None
    digits = [p for p in publish_date.replace(",", " ").split() if p.isdigit() and len(p) == 4]
    return int(digits[-1]) if digits else None
