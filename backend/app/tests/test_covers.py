import httpx
import respx

from app.tests.helpers import auth_headers, create_item

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d49444154789c626001000000ffff030000060005"
    "57bfabd40000000049454e44ae426082"
)


@respx.mock
def test_cover_is_downloaded_once_on_create(client):
    route = respx.get("https://covers.example.com/dune.jpg").mock(
        return_value=httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})
    )
    headers = auth_headers(client)
    item = create_item(client, headers, cover_url="https://covers.example.com/dune.jpg")
    assert route.call_count == 1
    assert item["cover_path"] == f"/media/covers/{item['id']}.png"
    assert item["metadata"]["cover_source_url"] == "https://covers.example.com/dune.jpg"

    from pathlib import Path

    from app.config import get_settings

    stored = Path(get_settings().media_dir) / "covers" / f"{item['id']}.png"
    assert stored.read_bytes() == PNG_BYTES


@respx.mock
def test_failed_cover_download_still_creates_item(client):
    respx.get("https://covers.example.com/broken.jpg").mock(
        return_value=httpx.Response(404)
    )
    headers = auth_headers(client)
    item = create_item(client, headers, cover_url="https://covers.example.com/broken.jpg")
    assert item["cover_path"] is None
    assert item["title"] == "Dune"


@respx.mock
def test_non_image_content_is_rejected(client):
    respx.get("https://covers.example.com/evil").mock(
        return_value=httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})
    )
    headers = auth_headers(client)
    item = create_item(client, headers, cover_url="https://covers.example.com/evil")
    assert item["cover_path"] is None
