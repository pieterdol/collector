"""Reading a cover with a vision model.

One backend-agnostic pipeline (photo → lines → search terms → catalog decides)
behind a swappable list of backends, so most of this is about ordering,
fallback and arbitration rather than about any one model.
"""

import io
import json

import httpx
import pytest
import respx
from PIL import Image

from app.config import get_settings
from app.core import vision
from app.db import SessionLocal
from app.models import Platform
from app.tests.helpers import auth_headers
from app.tests.test_providers import OPENLIB_SEARCH

OLLAMA = "http://ollama.test"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"

#: What gemma3:4b actually returned for the Days Gone box, ratings and all.
DAYS_GONE_BOX = "DAYS GONE\nOnly On PlayStation.\nPS4\n18\nwww.pegi.info\nBend Studio"


@pytest.fixture
def vision_env(monkeypatch):
    """Configure backends; clear the settings cache afterwards."""

    def _set(backends="gemini,ollama", **env):
        monkeypatch.setenv("VISION_BACKENDS", backends)
        monkeypatch.setenv("OLLAMA_URL", OLLAMA)
        monkeypatch.setenv("VISION_MODEL", "local-model")
        monkeypatch.setenv("GEMINI_API", "test-key")
        monkeypatch.setenv("GEMINI_VISION_MODEL", "flash-test")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


@pytest.fixture
def no_vision(monkeypatch):
    """Pin the feature off: a developer's own .env must not decide what these
    tests assert."""
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("GEMINI_API", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def photo(size=(60, 90)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "steelblue").save(buffer, format="JPEG")
    return buffer.getvalue()


def mock_ollama(text="", error=False):
    route = respx.post(f"{OLLAMA}/api/generate")
    if error:
        return route.mock(side_effect=httpx.ConnectError("refused"))
    return route.mock(return_value=httpx.Response(200, json={"response": text}))


def mock_gemini(text="", status=200):
    route = respx.post(url__startswith=f"{GEMINI}/flash-test")
    if status != 200:
        return route.mock(return_value=httpx.Response(status, json={"error": "nope"}))
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return route.mock(return_value=httpx.Response(200, json=body))


def mock_openlibrary(*titles_that_match: str):
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("q", "").lower()
        hit = any(term.lower() == query for term in titles_that_match)
        return httpx.Response(200, json=OPENLIB_SEARCH if hit else {"docs": []})

    return respx.get("https://openlibrary.org/search.json").mock(side_effect=handler)


def mock_igdb(monkeypatch, hits_only_when_filtered: bool):
    """IGDB, with a Platform row so the name maps to its id."""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "cid")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "secret")
    get_settings.cache_clear()
    respx.post("https://id.twitch.tv/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 5000})
    )
    with SessionLocal() as db:
        db.add(Platform(igdb_id=167, name="PlayStation 5"))
        db.commit()
    game = [{"id": 3, "name": "Stellar Blade", "platforms": [{"name": "PlayStation 5"}]}]

    def handler(request: httpx.Request) -> httpx.Response:
        # Substring, not "where platforms = (…)": a search that finds nothing
        # is retried as a name-contains lookup, where the same filter reads
        # "& platforms = (167)".
        filtered = "platforms = (167)" in request.content.decode()
        hit = filtered if hits_only_when_filtered else not filtered
        return httpx.Response(200, json=game if hit else [])

    return respx.post("https://api.igdb.com/v4/games").mock(side_effect=handler)


def post_photo(client, headers, type="book"):
    return client.post(
        f"/api/enrich/photo?type={type}",
        files={"file": ("cover.jpg", photo(), "image/jpeg")},
        headers=headers,
    )


# --- backend selection and fallback ------------------------------------


def test_photo_needs_a_backend(client, no_vision):
    res = post_photo(client, auth_headers(client))
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


@respx.mock
def test_the_first_configured_backend_wins(client, vision_env):
    """Gemini leads because it answers in ~1s; the local model isn't asked."""
    vision_env()
    gemini = mock_gemini("Dune")
    local = mock_ollama("Something Else")
    mock_openlibrary("Dune")
    assert post_photo(client, auth_headers(client)).json()["query"] == "Dune"
    assert gemini.called
    assert not local.called


@respx.mock
def test_a_throttled_backend_falls_through_to_the_next(client, vision_env):
    """The free tier sheds load; that must not fail the request."""
    vision_env()
    mock_gemini(status=429)
    local = mock_ollama("Dune")
    mock_openlibrary("Dune")
    assert post_photo(client, auth_headers(client)).json()["query"] == "Dune"
    assert local.called


@respx.mock
def test_a_backend_that_saw_nothing_falls_through_too(client, vision_env):
    """Answered, but empty — also a cue to try the next one."""
    vision_env()
    mock_gemini("")
    local = mock_ollama("Dune")
    mock_openlibrary("Dune")
    assert post_photo(client, auth_headers(client)).json()["query"] == "Dune"
    assert local.called


@respx.mock
def test_backend_order_is_configuration(client, vision_env):
    vision_env(backends="ollama,gemini")
    gemini = mock_gemini("Dune")
    local = mock_ollama("Dune")
    mock_openlibrary("Dune")
    post_photo(client, auth_headers(client))
    assert local.called
    assert not gemini.called


@respx.mock
def test_an_unconfigured_backend_is_skipped_not_tried(client, vision_env):
    vision_env(GEMINI_API="")
    local = mock_ollama("Dune")
    mock_openlibrary("Dune")
    assert post_photo(client, auth_headers(client)).json()["query"] == "Dune"
    assert local.called


@respx.mock
def test_every_backend_failing_is_reported(client, vision_env):
    vision_env()
    mock_gemini(status=503)
    mock_ollama(error=True)
    res = post_photo(client, auth_headers(client))
    assert res.status_code == 503
    assert "did not answer" in res.json()["detail"].lower()


def test_providers_reports_whether_vision_is_available(client, no_vision, vision_env):
    headers = auth_headers(client)
    assert client.get("/api/enrich/providers", headers=headers).json()["vision"] is False
    vision_env()
    assert client.get("/api/enrich/providers", headers=headers).json()["vision"] is True


# --- one read, three answers -------------------------------------------


@respx.mock
def test_the_title_is_confirmed_against_the_catalog(client, vision_env):
    vision_env()
    mock_gemini(DAYS_GONE_BOX)
    mock_openlibrary("DAYS GONE")
    body = post_photo(client, auth_headers(client)).json()
    assert body["query"] == "DAYS GONE"


@respx.mock
def test_ratings_and_urls_are_never_search_terms(client, vision_env):
    vision_env()
    mock_gemini(DAYS_GONE_BOX)
    mock_openlibrary()
    read = post_photo(client, auth_headers(client)).json()["read"]
    assert "18" not in read
    assert not [line for line in read if "pegi" in line.lower()]
    assert "Only On PlayStation" not in read


@respx.mock
def test_a_split_logo_is_offered_joined(client, vision_env):
    """Models order lines by size, so a two-word logo arrives as two lines."""
    vision_env()
    mock_gemini("BLADE\nPS5\nStellar\nSHIFT UP")
    mock_openlibrary("Stellar BLADE")  # only the joined, correctly-ordered form
    body = post_photo(client, auth_headers(client)).json()
    assert body["query"] == "Stellar BLADE"


def test_whole_phrases_are_tried_before_lone_words():
    """A lone word off a cover is usually a fragment, and the catalog will
    match it to the wrong game — "BLADE" finds a different Blade."""
    candidates = vision.candidates_from(["BLADE", "PS5", "Stellar", "SHIFT UP"])
    assert candidates.index("Stellar BLADE") < candidates.index("BLADE")
    assert candidates[0] == "SHIFT UP"  # the only whole phrase the model gave


@respx.mock
def test_a_game_search_is_narrowed_to_the_console_on_the_box(
    client, vision_env, monkeypatch
):
    vision_env()
    mock_gemini("Stellar Blade\nPS5\nSHIFT UP")
    mock_igdb(monkeypatch, hits_only_when_filtered=True)
    body = post_photo(client, auth_headers(client), type="game").json()
    assert body["query"] == "Stellar Blade"
    assert body["platform"] == "PlayStation 5"


@respx.mock
def test_a_console_that_did_not_help_is_dropped(client, vision_env, monkeypatch):
    """A misread console must not follow the user into the next search and
    filter it down to nothing."""
    vision_env()
    mock_gemini("Stellar Blade\nPS5")
    mock_igdb(monkeypatch, hits_only_when_filtered=False)
    body = post_photo(client, auth_headers(client), type="game").json()
    assert body["query"] == "Stellar Blade"
    assert body["platform"] is None


@respx.mock
def test_the_console_is_ignored_for_a_book(client, vision_env):
    """Only games can be narrowed by platform."""
    vision_env()
    mock_gemini("Dune\nPS4")
    mock_openlibrary("Dune")
    body = post_photo(client, auth_headers(client), type="book").json()
    assert body["platform"] is None


@respx.mock
def test_a_miss_still_reports_what_was_read(client, vision_env):
    """A near-miss must leave the user something to correct, not an empty box."""
    vision_env()
    mock_gemini("Letter Blade\nPS5")
    mock_openlibrary()
    body = post_photo(client, auth_headers(client)).json()
    assert body["query"] is None
    assert "Letter Blade" in body["read"]


# --- unit level --------------------------------------------------------


def test_prepare_image_downscales_for_the_model():
    prepared = vision.prepare_image(photo((4032, 3024)))
    assert max(Image.open(io.BytesIO(prepared)).size) == vision.MAX_EDGE


def test_prepare_image_uprights_a_sideways_photo():
    """Phones tag rotation instead of rotating pixels; models see pixels."""
    buffer = io.BytesIO()
    image = Image.new("RGB", (400, 300), "steelblue")
    exif = image.getexif()
    exif[274] = 6  # orientation: rotate 90° clockwise
    image.save(buffer, format="JPEG", exif=exif)
    prepared = Image.open(io.BytesIO(vision.prepare_image(buffer.getvalue())))
    assert prepared.size == (300, 400)  # portrait, as held


@pytest.mark.parametrize(
    "line, expected",
    [
        ("PS5", "PlayStation 5"),
        ("PS5.", "PlayStation 5"),
        ("PlayStation®5", "PlayStation 5"),
        ("ps 4", "PlayStation 4"),
        ("SHIFT UP", None),
        # The original console prints the bare wordmark. Every later Xbox
        # qualifies it, so the bare key can't swallow them: an unmapped
        # "XBOX 360" must stay a search term rather than resolve to Xbox.
        ("XBOX", "Xbox"),
        ("Xbox®", "Xbox"),
        ("XBOX 360", None),
    ],
)
def test_platform_from(line, expected):
    assert vision.platform_from([line]) == expected


@respx.mock
def test_read_cover_strips_markdown_the_model_wrapped_it_in(vision_env):
    """Some models answer in markdown; the bullets aren't part of the text."""
    vision_env(backends="gemini")
    mock_gemini("- DAYS GONE\n* PS4\n  # Bend Studio  ")
    assert vision.read_cover(photo()) == ["DAYS GONE", "PS4", "Bend Studio"]


@respx.mock
def test_the_prompt_asks_for_text_not_for_the_title(vision_env):
    """Asking "what is the title?" makes every model tested invent one for a
    photo with no title in frame. This guards the prompt, not the model."""
    vision_env(backends="ollama")
    route = mock_ollama("DAYS GONE")
    vision.read_cover(photo())
    prompt = json.loads(route.calls[0].request.content)["prompt"]
    assert "title" not in prompt.lower()
