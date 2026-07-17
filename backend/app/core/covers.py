"""Download a cover image exactly once, at item-creation time.

Covers are stored in the media volume and served from /media/covers/…,
so gallery views never hit external image hosts (faster, offline-friendly,
immune to dead links). The source URL is kept in item metadata.
"""

import uuid
from pathlib import Path

import httpx

from app.config import get_settings

MAX_BYTES = 5 * 1024 * 1024
_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def download_cover(url: str, item_id: uuid.UUID) -> str | None:
    """Fetch `url` into media/covers/{item_id}.{ext}; return the public path.

    Returns None on any failure — a missing cover must never block a save.
    """
    try:
        res = httpx.get(url, timeout=15, follow_redirects=True)
        res.raise_for_status()
    except httpx.HTTPError:
        return None

    content_type = res.headers.get("content-type", "").split(";")[0].strip()
    extension = _EXTENSIONS.get(content_type)
    if extension is None or len(res.content) > MAX_BYTES:
        return None

    covers_dir = Path(get_settings().media_dir) / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    (covers_dir / f"{item_id}{extension}").write_bytes(res.content)
    return f"/media/covers/{item_id}{extension}"
