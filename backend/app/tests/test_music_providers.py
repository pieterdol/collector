"""MusicBrainz + Discogs provider tests — external HTTP mocked with respx.

MusicBrainz needs no key, so it is the provider a fresh install gets;
Discogs takes over for everything once DISCOGS_TOKEN is set. Both paths
are covered here, the Discogs one without ever holding a real token.
"""

import httpx
import pytest
import respx

from app.config import get_settings
from app.db import SessionLocal
from app.domain.enums import ItemType
from app.providers import get_provider
from app.providers.formats import music_media


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def keys(monkeypatch):
    """Set provider keys for a test and reset the settings cache."""

    def _set(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


@pytest.fixture
def musicbrainz_only(keys):
    """No Discogs token: the composite provider must fall back to MusicBrainz."""
    keys(DISCOGS_TOKEN="")


KID_A_SEARCH = {
    "count": 1,
    "releases": [
        {
            "id": "b1392450-e666-3926-a536-22c65f834433",
            "score": 100,
            "title": "Kid A",
            "status": "Official",
            "artist-credit": [{"name": "Radiohead", "artist": {"name": "Radiohead"}}],
            "release-group": {"primary-type": "Album", "id": "rg-1"},
            "date": "2000-10-02",
            "country": "GB",
            "barcode": "724352773824",
            "label-info": [
                {"catalog-number": "7243 5 27753 1 4", "label": {"name": "Parlophone"}}
            ],
            "track-count": 10,
            "media": [{"format": '12" Vinyl', "disc-count": 2, "track-count": 10}],
        }
    ],
}

KID_A_RELEASE = {
    "id": "b1392450-e666-3926-a536-22c65f834433",
    "title": "Kid A",
    "date": "2000-10-02",
    "country": "GB",
    "barcode": "724352773824",
    "artist-credit": [{"name": "Radiohead", "artist": {"name": "Radiohead"}}],
    "release-group": {"primary-type": "Album", "id": "rg-1"},
    "label-info": [{"catalog-number": "7243 5 27753 1 4", "label": {"name": "Parlophone"}}],
    "media": [
        {
            "format": '12" Vinyl',
            "position": 1,
            "track-count": 2,
            "tracks": [
                {
                    "position": 1,
                    "number": "A1",
                    "title": "Everything in Its Right Place",
                    "length": 251000,
                },
                {"position": 2, "number": "A2", "title": "Kid A", "length": 444000},
            ],
        }
    ],
}


# --- format normalisation ---------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (('12" Vinyl',), 'Vinyl 12"'),
        (('7" Vinyl',), 'Vinyl 7"'),
        (('10" Vinyl',), 'Vinyl 10"'),
        (("Vinyl",), "Vinyl LP"),
        # Discogs reports a name plus descriptions; an album pressed on a
        # 12" record is an LP, not a 12" single.
        (("Vinyl", 'LP, Album, 12"'), "Vinyl LP"),
        (("Vinyl", '12", 45 RPM, Single'), 'Vinyl 12"'),
        (("CD",), "CD"),
        (("Hybrid SACD",), "CD"),
        (("Cassette",), "Cassette"),
        (("Digital Media",), None),
        ((None,), None),
        ((), None),
    ],
)
def test_music_media_normalises_provider_formats(raw, expected):
    assert music_media(*raw) == expected


# --- MusicBrainz -----------------------------------------------------------


@respx.mock
def test_musicbrainz_search_maps_pressing_details(db, musicbrainz_only):
    route = respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json=KID_A_SEARCH)
    )
    provider = get_provider(ItemType.MUSIC, db)
    assert provider.available  # keyless: music search works out of the box
    results = provider.search("kid a")

    assert len(results) == 1
    r = results[0]
    assert r.title == "Kid A"
    assert r.item_type == ItemType.MUSIC
    assert r.metadata["artist"] == "Radiohead"
    assert r.metadata["year"] == 2000
    assert r.metadata["release_date"] == "2000-10-02"
    assert r.metadata["label"] == "Parlophone"
    assert r.metadata["catalog_number"] == "7243 5 27753 1 4"
    assert r.metadata["barcode"] == "724352773824"
    assert r.metadata["country"] == "GB"
    assert r.metadata["media"] == 'Vinyl 12"'
    assert r.metadata["track_count"] == 10
    assert r.metadata["release_type"] == "Album"
    assert r.metadata["mb_release_id"] == "b1392450-e666-3926-a536-22c65f834433"
    # Namespaced so the composite provider can route details/relink calls.
    assert r.external_id == "mb:b1392450-e666-3926-a536-22c65f834433"
    assert r.cover_url == (
        "https://coverartarchive.org/release/b1392450-e666-3926-a536-22c65f834433/front-500"
    )
    # MusicBrainz blocks requests without a descriptive User-Agent.
    agent = route.calls[0].request.headers["user-agent"]
    assert "Collector" in agent


@respx.mock
def test_musicbrainz_search_asks_for_json_and_a_release_query(db, musicbrainz_only):
    route = respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json=KID_A_SEARCH)
    )
    get_provider(ItemType.MUSIC, db).search('kid "a"')
    request = route.calls[0].request
    assert request.url.params["fmt"] == "json"
    # Quotes would break Lucene's parser and 400 the whole search.
    assert '"' not in request.url.params["query"]


@respx.mock
def test_musicbrainz_details_adds_the_tracklist(db, musicbrainz_only):
    respx.get(
        "https://musicbrainz.org/ws/2/release/b1392450-e666-3926-a536-22c65f834433"
    ).mock(return_value=httpx.Response(200, json=KID_A_RELEASE))
    result = get_provider(ItemType.MUSIC, db).details(
        "mb:b1392450-e666-3926-a536-22c65f834433"
    )
    assert result is not None
    assert result.title == "Kid A"
    assert result.metadata["artist"] == "Radiohead"
    assert result.metadata["media"] == 'Vinyl 12"'
    assert result.metadata["tracks"] == [
        {"position": "A1", "title": "Everything in Its Right Place", "length": "4:11"},
        {"position": "A2", "title": "Kid A", "length": "7:24"},
    ]
    assert result.metadata["track_count"] == 2


@respx.mock
def test_musicbrainz_barcode_lookup_matches_a_release(db, musicbrainz_only):
    route = respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json=KID_A_SEARCH)
    )
    result = get_provider(ItemType.MUSIC, db).lookup_barcode("724352773824")
    assert result is not None
    assert result.title == "Kid A"
    assert "barcode:724352773824" in route.calls[0].request.url.params["query"]


@respx.mock
def test_musicbrainz_barcode_miss_returns_none(db, musicbrainz_only):
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json={"count": 0, "releases": []})
    )
    assert get_provider(ItemType.MUSIC, db).lookup_barcode("000000000000") is None


@respx.mock
def test_musicbrainz_error_degrades_to_empty_results(db, musicbrainz_only):
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(503)
    )
    assert get_provider(ItemType.MUSIC, db).search("kid a") == []


@respx.mock
def test_musicbrainz_search_is_cached(db, musicbrainz_only):
    route = respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json=KID_A_SEARCH)
    )
    provider = get_provider(ItemType.MUSIC, db)
    provider.search("cached album")
    provider.search("cached album")
    assert route.call_count == 1  # second hit served from provider_cache


@respx.mock
def test_musicbrainz_release_without_media_has_no_format(db, musicbrainz_only):
    """Digital-only and sparse releases must not crash the mapper."""
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(
            200,
            json={"releases": [{"id": "x-1", "title": "Sparse", "score": 90}]},
        )
    )
    result = get_provider(ItemType.MUSIC, db).search("sparse")[0]
    assert result.title == "Sparse"
    assert result.metadata["media"] is None
    assert result.metadata["artist"] is None
    assert result.metadata["year"] is None


@respx.mock
def test_musicbrainz_ranks_the_artist_you_named_first(db, musicbrainz_only):
    """MusicBrainz scores on text overlap alone, so "radiohead kid a" puts
    tribute albums (whose *titles* contain both words) above Radiohead's own
    record. Matching the artist has to outrank a better text score."""
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(
            200,
            json={
                "releases": [
                    {
                        "id": "tribute-1",
                        "title": "Radiohead's Kid A: Re-imagined",
                        "score": 100,
                        "artist-credit": [{"name": "Alex Schaaf"}],
                    },
                    {
                        "id": "real-1",
                        "title": "Kid A",
                        "score": 54,
                        "artist-credit": [{"name": "Radiohead"}],
                    },
                    {
                        "id": "real-2",
                        "title": "Kid A",
                        "score": 50,
                        "artist-credit": [{"name": "Radiohead"}],
                    },
                ]
            },
        )
    )
    results = get_provider(ItemType.MUSIC, db).search("radiohead kid a")
    assert [r.metadata["mb_release_id"] for r in results] == ["real-1", "real-2", "tribute-1"]


@respx.mock
def test_musicbrainz_keeps_score_order_when_no_artist_matches(db, musicbrainz_only):
    """Searching an album title alone must not reshuffle MusicBrainz's own
    ranking — there is no artist signal to add."""
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(
            200,
            json={
                "releases": [
                    {"id": "a", "title": "Kid A", "score": 100,
                     "artist-credit": [{"name": "Radiohead"}]},
                    {"id": "b", "title": "Kid A Reworked", "score": 60,
                     "artist-credit": [{"name": "Someone Else"}]},
                ]
            },
        )
    )
    results = get_provider(ItemType.MUSIC, db).search("kid a")
    assert [r.metadata["mb_release_id"] for r in results] == ["a", "b"]


@respx.mock
def test_musicbrainz_search_uses_the_dismax_parser(db, musicbrainz_only):
    """Plain typed words, not Lucene expressions — dismax is what the
    MusicBrainz site itself uses for that."""
    route = respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json=KID_A_SEARCH)
    )
    get_provider(ItemType.MUSIC, db).search("kid a")
    assert route.calls[0].request.url.params["dismax"] == "true"


@respx.mock
def test_musicbrainz_drops_placeholder_and_blank_fields(db, musicbrainz_only):
    """Self-released records carry MusicBrainz's literal "[no label]" row,
    and some releases carry an empty-string barcode. Neither is data."""
    respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(
            200,
            json={
                "releases": [
                    {
                        "id": "diy-1",
                        "title": "Demo Tape",
                        "score": 90,
                        "barcode": "",
                        "country": "",
                        "label-info": [
                            {"catalog-number": "[none]", "label": {"name": "[no label]"}}
                        ],
                    }
                ]
            },
        )
    )
    result = get_provider(ItemType.MUSIC, db).search("demo tape")[0]
    assert result.metadata["label"] is None
    assert result.metadata["catalog_number"] is None
    assert result.metadata["barcode"] is None
    assert result.metadata["country"] is None


# --- Discogs ---------------------------------------------------------------


DISCOGS_SEARCH = {
    "pagination": {"items": 1},
    "results": [
        {
            "id": 371000,
            "master_id": 22989,
            "title": "Radiohead - Kid A",
            "year": "2000",
            "country": "UK & Europe",
            "format": ["2x Vinyl", "LP", "Album", "Reissue"],
            "label": ["Parlophone", "EMI"],
            "catno": "7243 5 27753 1 4",
            "barcode": ["724352775316"],
            "thumb": "https://i.discogs.com/thumb.jpeg",
            "cover_image": "https://i.discogs.com/cover.jpeg",
        }
    ],
}

DISCOGS_RELEASE = {
    "id": 371000,
    "master_id": 22989,
    "title": "Kid A",
    "artists": [{"name": "Radiohead (2)"}],
    "year": 2000,
    "released": "2000-10-02",
    "country": "UK & Europe",
    "labels": [{"name": "Parlophone", "catno": "7243 5 27753 1 4"}],
    "formats": [{"name": "Vinyl", "qty": "2", "descriptions": ["LP", "Album"]}],
    "identifiers": [
        {"type": "Barcode", "value": "7 24352 77531 6"},
        {"type": "Matrix / Runout", "value": "KIDA-A1"},
    ],
    "tracklist": [
        {"position": "", "type_": "heading", "title": "Side A"},
        {"position": "A1", "type_": "track", "title": "Everything in Its Right Place",
         "duration": "4:11"},
        {"position": "A2", "type_": "track", "title": "Kid A", "duration": "4:44"},
    ],
    "images": [
        {"type": "secondary", "uri": "https://i.discogs.com/back.jpeg"},
        {"type": "primary", "uri": "https://i.discogs.com/front.jpeg"},
    ],
}


@pytest.fixture
def discogs(keys):
    """A configured Discogs token — the provider never sees a real one."""
    keys(DISCOGS_TOKEN="tok")


def test_music_falls_back_to_musicbrainz_without_a_discogs_token(db, musicbrainz_only):
    provider = get_provider(ItemType.MUSIC, db)
    assert provider.name == "musicbrainz"
    assert provider.available  # keyless, so never "not configured"


def test_discogs_takes_over_once_the_token_is_set(db, discogs):
    assert get_provider(ItemType.MUSIC, db).name == "discogs"


@respx.mock
def test_discogs_search_maps_pressing_details(db, discogs):
    route = respx.get("https://api.discogs.com/database/search").mock(
        return_value=httpx.Response(200, json=DISCOGS_SEARCH)
    )
    results = get_provider(ItemType.MUSIC, db).search("kid a")

    assert len(results) == 1
    r = results[0]
    # Discogs joins artist and album into one `title` field.
    assert r.title == "Kid A"
    assert r.metadata["artist"] == "Radiohead"
    assert r.metadata["year"] == 2000
    assert r.metadata["label"] == "Parlophone"
    assert r.metadata["catalog_number"] == "7243 5 27753 1 4"
    assert r.metadata["barcode"] == "724352775316"
    assert r.metadata["country"] == "UK & Europe"
    assert r.metadata["media"] == "Vinyl LP"
    assert r.metadata["release_type"] == "Album"
    assert r.metadata["discogs_release_id"] == 371000
    assert r.external_id == "discogs:371000"
    assert r.cover_url == "https://i.discogs.com/cover.jpeg"

    request = route.calls[0].request
    assert request.headers["authorization"] == "Discogs token=tok"
    assert "Collector" in request.headers["user-agent"]
    assert request.url.params["type"] == "release"


@respx.mock
def test_discogs_search_handles_a_title_without_an_artist(db, discogs):
    respx.get("https://api.discogs.com/database/search").mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 5, "title": "Untitled White Label"}]}
        )
    )
    result = get_provider(ItemType.MUSIC, db).search("white label")[0]
    assert result.title == "Untitled White Label"
    assert result.metadata["artist"] is None


@respx.mock
def test_discogs_details_adds_the_tracklist(db, discogs):
    respx.get("https://api.discogs.com/releases/371000").mock(
        return_value=httpx.Response(200, json=DISCOGS_RELEASE)
    )
    result = get_provider(ItemType.MUSIC, db).details("discogs:371000")
    assert result is not None
    # "Radiohead (2)" is a Discogs same-name disambiguator, not part of the name.
    assert result.metadata["artist"] == "Radiohead"
    assert result.metadata["release_date"] == "2000-10-02"
    assert result.metadata["media"] == "Vinyl LP"
    # Barcodes are printed spaced out on the sleeve; stored without spaces
    # so a scanned code matches. Matrix numbers are not barcodes.
    assert result.metadata["barcode"] == "724352775316"
    # Heading rows ("Side A") are not tracks.
    assert result.metadata["tracks"] == [
        {"position": "A1", "title": "Everything in Its Right Place", "length": "4:11"},
        {"position": "A2", "title": "Kid A", "length": "4:44"},
    ]
    assert result.metadata["track_count"] == 2
    assert result.cover_url == "https://i.discogs.com/front.jpeg"


@respx.mock
def test_discogs_barcode_lookup_matches_a_release(db, discogs):
    route = respx.get("https://api.discogs.com/database/search").mock(
        return_value=httpx.Response(200, json=DISCOGS_SEARCH)
    )
    result = get_provider(ItemType.MUSIC, db).lookup_barcode("724352775316")
    assert result is not None
    assert result.title == "Kid A"
    assert route.calls[0].request.url.params["barcode"] == "724352775316"


@respx.mock
def test_barcode_miss_in_discogs_still_tries_musicbrainz(db, discogs):
    """Two catalogues, two chances — a Discogs miss must not end the lookup."""
    respx.get("https://api.discogs.com/database/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    mb = respx.get("https://musicbrainz.org/ws/2/release").mock(
        return_value=httpx.Response(200, json=KID_A_SEARCH)
    )
    result = get_provider(ItemType.MUSIC, db).lookup_barcode("724352773824")
    assert result is not None
    assert result.external_id.startswith("mb:")
    assert mb.called


@respx.mock
def test_details_route_by_id_prefix_not_by_configuration(db, discogs):
    """An item matched in MusicBrainz stays re-linkable after Discogs
    arrives — the id says which catalogue owns it."""
    mb = respx.get(
        "https://musicbrainz.org/ws/2/release/b1392450-e666-3926-a536-22c65f834433"
    ).mock(return_value=httpx.Response(200, json=KID_A_RELEASE))
    discogs_route = respx.get("https://api.discogs.com/releases/371000").mock(
        return_value=httpx.Response(200, json=DISCOGS_RELEASE)
    )

    provider = get_provider(ItemType.MUSIC, db)
    assert provider.details("mb:b1392450-e666-3926-a536-22c65f834433").title == "Kid A"
    assert provider.details("discogs:371000").title == "Kid A"
    assert mb.called and discogs_route.called


@respx.mock
def test_discogs_error_degrades_to_empty_results(db, discogs):
    respx.get("https://api.discogs.com/database/search").mock(
        return_value=httpx.Response(429)  # Discogs rate limit
    )
    assert get_provider(ItemType.MUSIC, db).search("kid a") == []


def test_discogs_details_ignores_a_musicbrainz_id(db, discogs):
    """A malformed/foreign id must not become a request path."""
    from app.providers.discogs import DiscogsProvider

    assert DiscogsProvider(db).details("mb:not-a-number") is None
