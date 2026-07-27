"""MusicBrainz — music releases. No API key required.

Searches *releases*, not release-groups: an LP collector owns one specific
pressing (label, catalogue number, country, carrier), and that is the level
MusicBrainz models as a release. Cover art comes from the Cover Art
Archive, which is addressed by the same MBID.

MusicBrainz asks for two things in return for a keyless API: a descriptive
User-Agent, and at most one request per second. Both are honoured below;
repeat lookups never reach the network at all (provider_cache).

Docs: https://musicbrainz.org/doc/MusicBrainz_API
      https://musicbrainz.org/doc/Cover_Art_Archive/API
"""

import re
import time
import uuid

import httpx

from app.domain.enums import ItemType
from app.providers.base import MetadataProvider, MetadataResult
from app.providers.cache import cached_fetch
from app.providers.formats import music_media, track_length

SEARCH_URL = "https://musicbrainz.org/ws/2/release"
RELEASE_URL = "https://musicbrainz.org/ws/2/release/{mbid}"
COVER_URL = "https://coverartarchive.org/release/{mbid}/front-500"

# Identifies the app to MusicBrainz, as their API terms require.
USER_AGENT = "Collector/1.0 ( https://github.com/collector/collector )"

MIN_INTERVAL = 1.05  # seconds between live calls — MusicBrainz allows 1/s
_last_call: dict = {"at": 0.0}

# Lucene syntax characters. Dropped rather than escaped: an unbalanced
# quote or bracket in a typed title 400s the whole search.
_LUCENE = re.compile(r'["\\(){}\[\]^~:/!]')


def _throttle() -> None:
    elapsed = time.monotonic() - _last_call["at"]
    if 0 < elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    _last_call["at"] = time.monotonic()


def _get(url: str, params: dict) -> dict:
    _throttle()
    res = httpx.get(
        url,
        params={**params, "fmt": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
        follow_redirects=True,
    )
    res.raise_for_status()
    return res.json()


class MusicBrainzProvider(MetadataProvider):
    name = "musicbrainz"
    item_type = ItemType.MUSIC

    def search(self, query: str) -> list[MetadataResult]:
        clean = _LUCENE.sub(" ", query).strip()
        if not clean:
            return []

        def fetch() -> dict:
            # dismax is the parser the MusicBrainz site uses for typed words
            # (rather than Lucene expressions), and it ranks them better.
            return _get(SEARCH_URL, {"query": clean, "limit": 10, "dismax": "true"})

        try:
            data = cached_fetch(self.db, self.name, f"search:{clean.lower()}", fetch)
        except httpx.HTTPError:
            return []
        releases = _rank(data.get("releases", []), clean)
        return [self._map_release(r) for r in releases]

    def lookup_barcode(self, code: str) -> MetadataResult | None:
        """UPC/EAN → release. MusicBrainz indexes sleeve barcodes."""

        def fetch() -> dict:
            return _get(SEARCH_URL, {"query": f"barcode:{code}", "limit": 5})

        try:
            data = cached_fetch(self.db, self.name, f"barcode:{code}", fetch)
        except httpx.HTTPError:
            return None
        releases = data.get("releases", [])
        return self._map_release(releases[0]) if releases else None

    def details(self, external_id: str) -> MetadataResult | None:
        """One release by MBID, with the tracklist the search omits."""
        mbid = external_id.removeprefix("mb:")
        try:
            uuid.UUID(mbid)
        except ValueError:
            return None

        def fetch() -> dict:
            return _get(
                RELEASE_URL.format(mbid=mbid),
                {"inc": "artist-credits+labels+recordings+release-groups"},
            )

        try:
            data = cached_fetch(self.db, self.name, f"release:{mbid}", fetch)
        except httpx.HTTPError:
            return None
        if not data.get("id"):
            return None
        result = self._map_release(data)
        tracks = _tracks(data.get("media") or [])
        if tracks:
            result.metadata["tracks"] = tracks
            result.metadata["track_count"] = len(tracks)
        return result

    def _map_release(self, release: dict) -> MetadataResult:
        mbid = release.get("id")
        media = release.get("media") or []
        label_info = (release.get("label-info") or [{}])[0]
        group = release.get("release-group") or {}
        date = release.get("date") or group.get("first-release-date") or ""
        counted = sum(m.get("track-count") or 0 for m in media)
        return MetadataResult(
            title=release.get("title") or "Unknown",
            item_type=ItemType.MUSIC,
            metadata={
                "artist": _artist(release.get("artist-credit") or []),
                "mb_release_id": mbid,
                "mb_release_group_id": group.get("id"),
                "release_type": group.get("primary-type"),
                "year": int(date[:4]) if date[:4].isdigit() else None,
                "release_date": date if len(date) == 10 else None,
                "label": _clean((label_info.get("label") or {}).get("name")),
                "catalog_number": _clean(label_info.get("catalog-number")),
                "barcode": _clean(release.get("barcode")),
                "country": _clean(release.get("country")),
                "media": music_media(media[0].get("format") if media else None),
                "track_count": release.get("track-count") or counted or None,
            },
            cover_url=COVER_URL.format(mbid=mbid) if mbid else None,
            external_id=f"mb:{mbid}" if mbid else None,
        )


def _clean(value: str | None) -> str | None:
    """Drop blanks and MusicBrainz's bracketed placeholders.

    Self-released records carry a real label row named "[no label]", and
    "[none]" turns up as a catalogue number — neither is information.
    """
    if not value or not value.strip():
        return None
    text = value.strip()
    return None if text.startswith("[") else text


def _rank(releases: list[dict], query: str) -> list[dict]:
    """Put releases by an artist the user named above better text matches.

    MusicBrainz scores on text overlap, so "radiohead kid a" ranks a tribute
    album called "Radiohead's Kid A: Re-imagined" above Radiohead's own
    record. Whole-token artist matches break that tie; with no artist in the
    query nothing matches and MusicBrainz's own order stands.
    """
    tokens = set(re.findall(r"\w+", query.casefold()))

    def key(release: dict) -> tuple[int, int]:
        artist = (_artist(release.get("artist-credit") or []) or "").casefold()
        hits = len(tokens & set(re.findall(r"\w+", artist)))
        return (hits, int(release.get("score") or 0))

    return sorted(releases, key=key, reverse=True)


def _artist(credit: list) -> str | None:
    """Flatten an artist-credit list, keeping collaboration join phrases."""
    parts: list[str] = []
    for entry in credit:
        if isinstance(entry, str):
            parts.append(entry)
            continue
        parts.append(entry.get("name") or (entry.get("artist") or {}).get("name") or "")
        parts.append(entry.get("joinphrase") or "")
    return "".join(parts).strip() or None


def _tracks(media: list[dict]) -> list[dict]:
    """Flatten every disc/side into one tracklist.

    Vinyl positions are the side labels people actually read off the
    sleeve ("A1"); other carriers fall back to the running number.
    """
    out = []
    for medium in media:
        for track in medium.get("tracks") or []:
            title = track.get("title") or (track.get("recording") or {}).get("title")
            if not title:
                continue
            out.append(
                {
                    "position": str(track.get("number") or track.get("position") or ""),
                    "title": title,
                    "length": track_length(track.get("length")),
                }
            )
    return out
