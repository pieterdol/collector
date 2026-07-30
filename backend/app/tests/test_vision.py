"""Reading a title off a photographed cover (local Ollama).

Two models with opposite failure modes are asked, and the catalog decides
which answer was real — so these tests are mostly about arbitration.
"""

import io
import json

import httpx
import pytest
import respx
from PIL import Image

from app.config import get_settings
from app.core import vision
from app.tests.helpers import auth_headers
from app.tests.test_providers import OPENLIB_SEARCH

OLLAMA = "http://ollama.test"


@pytest.fixture
def vision_env(monkeypatch):
    """Configure a (mocked) local Ollama; clear the settings cache after."""

    def _set(**env):
        monkeypatch.setenv("OLLAMA_URL", OLLAMA)
        monkeypatch.setenv("VISION_MODEL", "reader-model")
        monkeypatch.setenv("VISION_RECOGNIZER_MODEL", "moondream")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


@pytest.fixture
def no_vision(monkeypatch):
    """Pin the feature off: a configured OLLAMA_URL in the developer's own
    .env must not decide what these tests assert."""
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def photo(size=(60, 90)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "steelblue").save(buffer, format="JPEG")
    return buffer.getvalue()


def mock_ollama(reader="", recognizer="", all_text=""):
    """One route for both models; the request says which is being asked."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "one per line" in body["prompt"]:
            answer = all_text
        elif body["model"].startswith("moondream"):
            answer = recognizer
        else:
            answer = reader
        return httpx.Response(200, json={"response": answer})

    return respx.post(f"{OLLAMA}/api/generate").mock(side_effect=handler)


def mock_openlibrary(*titles_that_match: str):
    """Open Library, answering only for the given search terms."""

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("q", "").lower()
        hit = any(term.lower() == query for term in titles_that_match)
        return httpx.Response(200, json=OPENLIB_SEARCH if hit else {"docs": []})

    return respx.get("https://openlibrary.org/search.json").mock(side_effect=handler)


def post_photo(client, headers, type="book"):
    return client.post(
        f"/api/enrich/photo?type={type}",
        files={"file": ("cover.jpg", photo(), "image/jpeg")},
        headers=headers,
    )


def test_photo_needs_vision_configured(client, no_vision):
    """No OLLAMA_URL: the feature is off, and says so."""
    res = post_photo(client, auth_headers(client))
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


@respx.mock
def test_photo_reads_the_title_and_confirms_it_against_the_catalog(client, vision_env):
    vision_env()
    mock_ollama(reader="Dune")
    mock_openlibrary("Dune")
    res = post_photo(client, auth_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "Dune"
    assert "Dune" in body["read"]


@respx.mock
def test_photo_prefers_the_answer_the_catalog_recognises(client, vision_env):
    """The reader's partial read misses; the recogniser's name lands."""
    vision_env()
    mock_ollama(reader="BLADE", recognizer="!!!Dune!!!")
    mock_openlibrary("Dune")  # "BLADE" finds nothing
    body = post_photo(client, auth_headers(client)).json()
    assert body["query"] == "Dune"
    assert body["read"] == ["BLADE", "Dune"]  # reader first, both offered


@respx.mock
def test_photo_pulls_a_title_out_of_the_recognizers_chatter(client, vision_env):
    """Moondream only answers in prose; the title is the quoted bit."""
    vision_env()
    mock_ollama(
        reader="",
        recognizer='The image shows a game case for "Dune" on a couch.',
    )
    mock_openlibrary("Dune")
    body = post_photo(client, auth_headers(client)).json()
    assert body["query"] == "Dune"


@respx.mock
def test_photo_still_reports_what_it_read_when_nothing_matches(client, vision_env):
    """A miss must leave the user something to correct, not an empty box."""
    vision_env()
    mock_ollama(reader="Letter Blade", recognizer="")
    mock_openlibrary()  # catalog knows nothing
    body = post_photo(client, auth_headers(client)).json()
    assert body["query"] is None
    assert body["read"] == ["Letter Blade"]


@respx.mock
def test_photo_falls_back_to_the_other_text_on_the_box(client, vision_env):
    """Unreadable title, but the publisher line is printed in clean type."""
    vision_env()
    mock_ollama(
        reader="Letter Blade",
        all_text="Letter BLADE\nSHIFT UP\nPS5\n18\nwww.pegi.info",
    )
    mock_openlibrary("SHIFT UP")
    body = post_photo(client, auth_headers(client)).json()
    assert body["query"] == "SHIFT UP"
    # Ratings and URLs are never search terms.
    assert "18" not in body["read"]
    assert not [line for line in body["read"] if "pegi" in line]


@respx.mock
def test_photo_reports_the_console_printed_on_the_box(client, vision_env):
    vision_env()
    mock_ollama(reader="Days Gone", all_text="DAYS GONE\nPS4\nbend STUDIO")
    mock_openlibrary()  # force the all-text pass, which carries the platform
    body = post_photo(client, auth_headers(client)).json()
    assert body["platform"] == "PlayStation 4"


@respx.mock
def test_photo_survives_a_model_that_is_not_answering(client, vision_env):
    vision_env()
    respx.post(f"{OLLAMA}/api/generate").mock(side_effect=httpx.ConnectError("refused"))
    res = post_photo(client, auth_headers(client))
    assert res.status_code == 503
    assert "ollama" in res.json()["detail"].lower()


def test_providers_reports_whether_vision_is_available(client, no_vision, vision_env):
    headers = auth_headers(client)
    assert client.get("/api/enrich/providers", headers=headers).json()["vision"] is False
    vision_env()
    body = client.get("/api/enrich/providers", headers=headers).json()
    assert body["vision"] is True


# --- unit level: the bits that don't need a request ---------------------


def test_prepare_image_downscales_for_the_model():
    """Big phone photos are slow and read worse — 1024px is the sweet spot."""
    prepared = vision.prepare_image(photo((4032, 3024)))
    assert max(Image.open(io.BytesIO(prepared)).size) == 1024


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
    "answer, expected",
    [
        ("Cyberpunk 2077", "Cyberpunk 2077"),
        ("!!!STELLAR BLADE!!!", "STELLAR BLADE"),
        ('"Days Gone"', "Days Gone"),
        ("The title is: Days Gone.", "Days Gone"),
        ('a case for "Ni no Kuni II" on a table', "Ni no Kuni II"),
        ("UNKNOWN", None),
        ("", None),
        ("   \n ", None),
    ],
)
def test_clean_answer(answer, expected):
    assert vision.clean_answer(answer) == expected
