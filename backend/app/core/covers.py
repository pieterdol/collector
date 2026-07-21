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


def download_image(url: str, dest_dir: Path, stem: str) -> str | None:
    """Fetch `url` into dest_dir/{stem}.{ext}; return the public /media path.

    dest_dir must live under the media volume. Returns None on any
    failure — a missing image must never block a save.
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

    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{stem}{extension}").write_bytes(res.content)
    relative = (dest_dir / f"{stem}{extension}").relative_to(Path(get_settings().media_dir))
    return f"/media/{relative}"


def download_cover(url: str, item_id: uuid.UUID) -> str | None:
    """Fetch `url` into media/covers/{item_id}.{ext}; return the public path."""
    return download_image(url, Path(get_settings().media_dir) / "covers", str(item_id))
