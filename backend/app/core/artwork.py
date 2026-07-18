"""Hero art, screenshots and descriptions — fetched once per item.

Sources, in order of preference:
  game  + steam_appid → Steam store appdetails (keyless) + Steam CDN hero
  game  + igdb_id     → IGDB artworks/screenshots/summary (Twitch creds)
  movie + tmdb_id     → TMDB /images backdrops; description = stored overview
  book                → nothing to fetch (cover-only layout)

Results are stored in item.meta:
  artwork_fetched: True, hero_path, screenshot_paths[], description
Files live in media/artwork/{item_id}/. On provider failure the flag is NOT
set, so opening the item again retries.
"""

import uuid
from pathlib import Path

import httpx

from app.config import get_settings
from app.models import Item
from app.providers.cache import cached_fetch
from app.providers.igdb import IgdbProvider

MAX_SHOTS = 5
MAX_BYTES = 10 * 1024 * 1024
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"
STEAM_HERO = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_hero.jpg"
IGDB_IMAGE = "https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg"
TMDB_IMAGE = "https://image.tmdb.org/t/p/w1280{path}"


def fetch_artwork(db, item: Item) -> bool:
    """Populate hero/screenshots/description once. Returns True if updated."""
    if item.meta.get("artwork_fetched"):
        return False

    if item.type == "game" and item.meta.get("steam_appid"):
        found = _from_steam(db, item)
    elif item.type == "game" and item.meta.get("igdb_id"):
        found = _from_igdb(db, item)
    elif item.type == "movie" and item.meta.get("tmdb_id"):
        found = _from_tmdb(db, item)
    else:
        found = {}  # books and manual items: nothing to fetch, mark done

    if found is None:
        return False  # provider error → retry on a later visit

    hero_path = _download(found.get("hero_url"), item.id, "hero")
    shot_paths = [
        p
        for i, url in enumerate(found.get("shot_urls", [])[:MAX_SHOTS])
        if (p := _download(url, item.id, f"shot{i}"))
    ]

    meta = {**item.meta, "artwork_fetched": True}
    if hero_path:
        meta["hero_path"] = hero_path
    if shot_paths:
        meta["screenshot_paths"] = shot_paths
    if found.get("description") and not meta.get("description"):
        meta["description"] = found["description"]
    if found.get("release_date") and not meta.get("release_date"):
        meta["release_date"] = found["release_date"]
    item.meta = meta
    db.commit()
    return True


def _from_steam(db, item: Item) -> dict | None:
    appid = item.meta["steam_appid"]

    def fetch() -> dict:
        res = httpx.get(STEAM_APPDETAILS, params={"appids": appid, "l": "english"}, timeout=15)
        res.raise_for_status()
        return res.json()

    try:
        data = cached_fetch(db, "steam_store", f"appdetails:{appid}", fetch)
    except httpx.HTTPError:
        return None
    entry = (data or {}).get(str(appid), {})
    if not entry.get("success"):
        return {}  # delisted app: nothing available, don't retry forever
    details = entry.get("data", {})
    return {
        "hero_url": STEAM_HERO.format(appid=appid),
        "shot_urls": [s["path_full"] for s in details.get("screenshots", []) if s.get("path_full")],
        "description": details.get("short_description"),
        "release_date": _parse_steam_date((details.get("release_date") or {}).get("date")),
    }


def _parse_steam_date(raw: str | None) -> str | None:
    """Steam formats dates like '24 Feb, 2017' (locale-dependent variants exist)."""
    if not raw:
        return None
    from datetime import datetime

    for fmt in ("%d %b, %Y", "%b %d, %Y", "%d %B, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _from_igdb(db, item: Item) -> dict | None:
    provider = IgdbProvider(db)
    if not provider.available:
        return {}
    igdb_id = item.meta["igdb_id"]

    def fetch() -> dict:
        body = (
            f"where id = {int(igdb_id)}; "
            "fields summary,artworks.image_id,screenshots.image_id; limit 1;"
        )
        res = httpx.post(
            "https://api.igdb.com/v4/games",
            content=body,
            headers={
                "Client-ID": get_settings().twitch_client_id,
                "Authorization": f"Bearer {provider._token()}",
            },
            timeout=15,
        )
        res.raise_for_status()
        return {"games": res.json()}

    try:
        data = cached_fetch(db, "igdb", f"artwork:{igdb_id}", fetch)
    except httpx.HTTPError:
        return None
    games = data.get("games", [])
    if not games:
        return {}
    game = games[0]
    artworks = [a["image_id"] for a in game.get("artworks", []) if a.get("image_id")]
    shots = [s["image_id"] for s in game.get("screenshots", []) if s.get("image_id")]
    return {
        "hero_url": IGDB_IMAGE.format(size="1080p", image_id=artworks[0]) if artworks else (
            IGDB_IMAGE.format(size="1080p", image_id=shots[0]) if shots else None
        ),
        "shot_urls": [IGDB_IMAGE.format(size="screenshot_big", image_id=s) for s in shots],
        "description": game.get("summary"),
    }


def _from_tmdb(db, item: Item) -> dict | None:
    api_key = get_settings().tmdb_api_key
    if not api_key:
        return {}
    tmdb_id = item.meta["tmdb_id"]

    def fetch() -> dict:
        res = httpx.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}/images",
            params={"api_key": api_key},
            timeout=15,
        )
        res.raise_for_status()
        return res.json()

    try:
        data = cached_fetch(db, "tmdb", f"images:{tmdb_id}", fetch)
    except httpx.HTTPError:
        return None
    backdrops = [b["file_path"] for b in data.get("backdrops", []) if b.get("file_path")]
    return {
        "hero_url": TMDB_IMAGE.format(path=backdrops[0]) if backdrops else None,
        "shot_urls": [TMDB_IMAGE.format(path=p) for p in backdrops[1 : MAX_SHOTS + 1]],
        # TMDB overview is captured at add time; artwork adds nothing textual.
        "description": item.meta.get("overview"),
    }


def _download(url: str | None, item_id: uuid.UUID, name: str) -> str | None:
    if not url:
        return None
    try:
        res = httpx.get(url, timeout=20, follow_redirects=True)
        res.raise_for_status()
    except httpx.HTTPError:
        return None
    ext = _EXT.get(res.headers.get("content-type", "").split(";")[0].strip())
    if ext is None or len(res.content) > MAX_BYTES:
        return None
    directory = Path(get_settings().media_dir) / "artwork" / str(item_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}{ext}").write_bytes(res.content)
    return f"/media/artwork/{item_id}/{name}{ext}"
