"""Steam Web API client — used by the bulk import, not the enrich flow.

Docs: https://developer.valvesoftware.com/wiki/Steam_Web_API
"""

import httpx

from app.config import get_settings

BASE = "https://api.steampowered.com"
# 2:3 poster used by the Steam library UI; matches our poster grid.
LIBRARY_COVER = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg"


class SteamError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def _key() -> str:
    key = get_settings().steam_api_key
    if not key:
        raise SteamError(503, "Steam import is not configured (STEAM_API_KEY is missing)")
    return key


def resolve_steam_id(steam_id_or_vanity: str) -> str:
    """Accept a 17-digit SteamID64 or a vanity name and return the SteamID64."""
    candidate = steam_id_or_vanity.strip().rstrip("/").split("/")[-1]
    if len(candidate) == 17 and candidate.isdigit():
        return candidate
    res = httpx.get(
        f"{BASE}/ISteamUser/ResolveVanityURL/v0001/",
        params={"key": _key(), "vanityurl": candidate},
        timeout=15,
    )
    res.raise_for_status()
    payload = res.json().get("response", {})
    if payload.get("success") != 1:
        raise SteamError(404, f"No Steam profile found for '{candidate}'")
    return payload["steamid"]


def owned_games(steam_id: str) -> list[dict]:
    """Return [{appid, name, playtime_forever(minutes)}, …] for a profile."""
    res = httpx.get(
        f"{BASE}/IPlayerService/GetOwnedGames/v0001/",
        params={
            "key": _key(),
            "steamid": steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "format": "json",
        },
        timeout=30,
    )
    res.raise_for_status()
    payload = res.json().get("response", {})
    if "games" not in payload:
        raise SteamError(
            400,
            "Steam returned no games — the profile's game details are probably "
            "set to private (Steam profile → Privacy Settings → Game details).",
        )
    return payload["games"]
