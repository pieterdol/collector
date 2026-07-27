"""Discogs — music releases, pressing by pressing. Requires DISCOGS_TOKEN.

Discogs is the deepest catalogue of *physical* records: every release row
is one actual pressing, with its label, catalogue number, country and
carrier. It needs a personal access token (Settings → Developers on
discogs.com), which is why MusicBrainz stays the keyless default and this
provider takes over only once the token exists.

Metadata keys match the MusicBrainz mapper exactly, so the UI never has to
know which catalogue an album came from.

Docs: https://www.discogs.com/developers/#page:database
"""

import re

import httpx

from app.config import get_settings
from app.domain.enums import ItemType
from app.providers.base import MetadataProvider, MetadataResult
from app.providers.cache import cached_fetch
from app.providers.formats import music_media

SEARCH_URL = "https://api.discogs.com/database/search"
RELEASE_URL = "https://api.discogs.com/releases/{release_id}"

USER_AGENT = "Collector/1.0 +https://github.com/collector/collector"

# Descriptions Discogs uses for the kind of release, in the order we'd
# rather report them (a "Single, Reissue" is a single).
RELEASE_TYPES = ("Album", "EP", "Single", "Compilation", "Mini-Album", "Maxi-Single")

# Discogs disambiguates same-named artists as "Nirvana (2)".
_DISAMBIGUATOR = re.compile(r"\s*\(\d+\)$")


class DiscogsProvider(MetadataProvider):
    name = "discogs"
    item_type = ItemType.MUSIC

    @property
    def available(self) -> bool:
        return bool(get_settings().discogs_token)

    def _get(self, url: str, params: dict) -> dict:
        res = httpx.get(
            url,
            params=params,
            headers={
                "Authorization": f"Discogs token={get_settings().discogs_token}",
                "User-Agent": USER_AGENT,
            },
            timeout=10,
        )
        res.raise_for_status()
        return res.json()

    def search(self, query: str) -> list[MetadataResult]:
        if not self.available:
            return []

        def fetch() -> dict:
            return self._get(
                SEARCH_URL, {"q": query, "type": "release", "per_page": 10}
            )

        try:
            data = cached_fetch(self.db, self.name, f"search:{query.lower()}", fetch)
        except httpx.HTTPError:
            return []
        return [self._map_search(r) for r in data.get("results", [])]

    def lookup_barcode(self, code: str) -> MetadataResult | None:
        if not self.available:
            return None

        def fetch() -> dict:
            return self._get(
                SEARCH_URL, {"barcode": code, "type": "release", "per_page": 5}
            )

        try:
            data = cached_fetch(self.db, self.name, f"barcode:{code}", fetch)
        except httpx.HTTPError:
            return None
        results = data.get("results", [])
        return self._map_search(results[0]) if results else None

    def details(self, external_id: str) -> MetadataResult | None:
        """One release by Discogs id, with the tracklist the search omits."""
        release_id = external_id.removeprefix("discogs:")
        if not self.available or not release_id.isdigit():
            return None

        def fetch() -> dict:
            return self._get(RELEASE_URL.format(release_id=int(release_id)), {})

        try:
            data = cached_fetch(self.db, self.name, f"release:{release_id}", fetch)
        except httpx.HTTPError:
            return None
        return self._map_release(data) if data.get("id") else None

    def _map_search(self, entry: dict) -> MetadataResult:
        """Search rows carry no separate artist field — Discogs joins them
        into `title` as "Artist - Album", which is what we split back out."""
        artist, _, title = (entry.get("title") or "").partition(" - ")
        if not title:  # no separator: treat the whole string as the title
            artist, title = "", artist
        formats = entry.get("format") or []
        year = entry.get("year")
        return MetadataResult(
            title=title.strip() or "Unknown",
            item_type=ItemType.MUSIC,
            metadata={
                "artist": _clean_artist(artist),
                "discogs_release_id": entry.get("id"),
                "discogs_master_id": entry.get("master_id") or None,
                "release_type": _release_type(formats),
                "year": int(year) if str(year).isdigit() else None,
                "release_date": None,  # search rows only carry the year
                "label": (entry.get("label") or [None])[0],
                "catalog_number": entry.get("catno") or None,
                "barcode": (entry.get("barcode") or [None])[0],
                "country": entry.get("country"),
                "media": music_media(*formats),
                "track_count": None,
            },
            cover_url=entry.get("cover_image") or entry.get("thumb") or None,
            external_id=f"discogs:{entry.get('id')}" if entry.get("id") else None,
        )

    def _map_release(self, release: dict) -> MetadataResult:
        formats = release.get("formats") or [{}]
        descriptions = [d for f in formats for d in (f.get("descriptions") or [])]
        label_info = (release.get("labels") or [{}])[0]
        released = str(release.get("released") or "")
        year = release.get("year")
        tracks = _tracks(release.get("tracklist") or [])
        images = release.get("images") or []
        return MetadataResult(
            title=release.get("title") or "Unknown",
            item_type=ItemType.MUSIC,
            metadata={
                "artist": _clean_artist(
                    ", ".join(a.get("name", "") for a in release.get("artists") or [])
                ),
                "discogs_release_id": release.get("id"),
                "discogs_master_id": release.get("master_id") or None,
                "release_type": _release_type(descriptions),
                "year": int(year) if str(year).isdigit() else None,
                "release_date": released if len(released) == 10 else None,
                "label": label_info.get("name"),
                "catalog_number": label_info.get("catno") or None,
                "barcode": _barcode(release.get("identifiers") or []),
                "country": release.get("country"),
                "media": music_media(formats[0].get("name"), *descriptions),
                "track_count": len(tracks) or None,
                "tracks": tracks,
            },
            cover_url=_primary_image(images),
            external_id=f"discogs:{release.get('id')}" if release.get("id") else None,
        )


def _clean_artist(name: str) -> str | None:
    return _DISAMBIGUATOR.sub("", name.strip()) or None


def _release_type(descriptions: list[str]) -> str | None:
    lowered = {d.lower() for d in descriptions}
    return next((t for t in RELEASE_TYPES if t.lower() in lowered), None)


def _barcode(identifiers: list[dict]) -> str | None:
    for entry in identifiers:
        if (entry.get("type") or "").lower() == "barcode" and entry.get("value"):
            # Sleeves print barcodes spaced out ("7 24352 77381 4").
            return entry["value"].replace(" ", "")
    return None


def _primary_image(images: list[dict]) -> str | None:
    primary = next((i for i in images if i.get("type") == "primary"), None)
    return (primary or (images[0] if images else {})).get("uri") or None


def _tracks(tracklist: list[dict]) -> list[dict]:
    """Real tracks only — Discogs mixes in heading rows for sides/sub-works."""
    return [
        {
            "position": str(track.get("position") or ""),
            "title": track["title"],
            "length": track.get("duration") or None,
        }
        for track in tracklist
        if track.get("title") and track.get("type_", "track") == "track"
    ]
