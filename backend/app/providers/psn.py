"""PSN client — used by the bulk import, not the enrich flow.

Sony has no official public API; this is the flow the PlayStation App
itself uses, as documented by the psn-api and PSNAWP communities. The
user pastes their NPSSO cookie (playstation.com sign-in →
ca.account.sony.com/api/v1/ssocookie); we exchange it for a short-lived
access token and query the purchased-games GraphQL. The token is used
once per import and never stored.
"""

from urllib.parse import parse_qs, urlparse

import httpx

AUTH_BASE = "https://ca.account.sony.com/api"
GRAPHQL_URL = "https://web.np.playstation.com/api/graphql/v1/op"

# The PlayStation App's public OAuth client (id:secret, base64) and
# redirect — constants every community PSN library ships with.
_CLIENT_ID = "09515159-7237-4370-9b40-3806e67c0891"
_CLIENT_BASIC = "MDk1MTUxNTktNzIzNy00MzcwLTliNDAtMzgwNmU2N2MwODkxOnVjUGprYTV0bnRCMktxc1A="
_REDIRECT_URI = "com.scee.psxandroid.scecompcall://redirect"

# Persisted-query hash of the web library's getPurchasedGameList.
_PURCHASED_HASH = "2c045408b0a4d0264bb5a3edfed4efd49fb4749cf8d216be9043768adff905e2"
_PAGE_SIZE = 100


class PsnError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def exchange_npsso(npsso: str) -> str:
    """NPSSO cookie → access token (authorization-code flow)."""
    res = httpx.get(
        f"{AUTH_BASE}/authz/v3/oauth/authorize",
        params={
            "access_type": "offline",
            "client_id": _CLIENT_ID,
            "response_type": "code",
            "scope": "psn:mobile.v2.core psn:clientapp",
            "redirect_uri": _REDIRECT_URI,
        },
        cookies={"npsso": npsso.strip()},
        follow_redirects=False,
        timeout=15,
    )
    query = parse_qs(urlparse(res.headers.get("location", "")).query)
    code = (query.get("code") or [None])[0]
    if not code:
        raise PsnError(
            401,
            "NPSSO token was rejected — sign in at playstation.com, open "
            "ca.account.sony.com/api/v1/ssocookie and copy a fresh value.",
        )
    res = httpx.post(
        f"{AUTH_BASE}/authz/v3/oauth/token",
        data={
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": _REDIRECT_URI,
            "token_format": "jwt",
        },
        headers={"Authorization": f"Basic {_CLIENT_BASIC}"},
        timeout=15,
    )
    if res.status_code != 200:
        raise PsnError(502, "PSN sign-in failed while exchanging the NPSSO token")
    return res.json()["access_token"]


def purchased_games(token: str, include_ps_plus: bool = False) -> list[dict]:
    """Purchased titles, each with `subscription` set for PS Plus claims.

    Sony tags every entitlement with how it was obtained, so the
    subscription-gated "free monthly games" are a separate, exact list.
    """
    games = _fetch_list(token, "NONE")
    for game in games:
        game["subscription"] = None
    if include_ps_plus:
        plus = _fetch_list(token, "PS_PLUS")
        for game in plus:
            game["subscription"] = "PS Plus"
        games += plus
    return games


def _fetch_list(token: str, subscription_service: str) -> list[dict]:
    out: list[dict] = []
    while True:
        res = httpx.post(
            GRAPHQL_URL,
            json={
                "operationName": "getPurchasedGameList",
                "variables": {
                    "isPublic": False,
                    "size": _PAGE_SIZE,
                    "start": len(out),
                    "sortBy": "productName",
                    "sortDirection": "asc",
                    "subscriptionService": subscription_service,
                },
                "extensions": {
                    "persistedQuery": {"version": 1, "sha256Hash": _PURCHASED_HASH}
                },
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        res.raise_for_status()
        payload = (res.json().get("data") or {}).get("purchasedTitlesRetrieve") or {}
        page = payload.get("games") or []
        out.extend(g for g in page if isinstance(g, dict))
        total = (payload.get("pageInfo") or {}).get("totalCount", len(out))
        if not page or len(out) >= total:
            return out
