"""TTL cache for provider lookups, stored in the provider_cache table.

Repeated searches (retyping, another user, a re-run Steam import) never
re-hit the external API within the TTL.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ProviderCache


def cached_fetch(
    db: Session, provider: str, query_key: str, fetch: Callable[[], dict], force: bool = False
) -> dict:
    """Return the cached response for (provider, query_key), fetching on miss.

    `force` re-fetches even on a hit — only for user-initiated refreshes of
    data that legitimately grows (a running show's episode list).
    """
    now = datetime.now(UTC)
    row = db.scalar(
        select(ProviderCache).where(
            ProviderCache.provider == provider, ProviderCache.query_key == query_key
        )
    )
    if not force and row is not None and (row.expires_at is None or row.expires_at > now):
        return row.response

    response = fetch()

    ttl = timedelta(hours=get_settings().provider_cache_ttl_hours)
    if row is None:
        row = ProviderCache(provider=provider, query_key=query_key)
        db.add(row)
    row.response = response
    row.fetched_at = now
    row.expires_at = now + ttl
    db.commit()
    return response
