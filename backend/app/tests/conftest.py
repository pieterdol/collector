"""Shared test fixtures.

Tests run against a real PostgreSQL (JSONB, tsvector and CHECK constraints
are part of what we're testing) — but ALWAYS against a dedicated `*_test`
database, never the configured one. That makes `docker compose exec backend
pytest` safe: it creates collector_test next to the real collector DB.
"""

import os

# Derive the test database from DATABASE_URL before app modules read it.
_raw = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:test@localhost:5433/collector"
)
_base, _name = _raw.rsplit("/", 1)
if not _name.endswith("_test"):
    _name = f"{_name}_test"
os.environ["DATABASE_URL"] = f"{_base}/{_name}"
os.environ.setdefault("MEDIA_DIR", "/tmp/collector-test-media")

# The suite assumes a credential-free baseline (so `docker compose exec
# backend pytest` works even when the container has real keys); tests that
# need credentials set them via monkeypatch + get_settings.cache_clear().
for _key in (
    "TMDB_API_KEY",
    "TWITCH_CLIENT_ID",
    "TWITCH_CLIENT_SECRET",
    "STEAM_API_KEY",
    "DISCOGS_TOKEN",
):
    os.environ.pop(_key, None)


def _ensure_test_db() -> None:
    from sqlalchemy import create_engine, text

    admin = create_engine(f"{_base}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_name}"'))
    admin.dispose()


_ensure_test_db()

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401  (register all tables on Base.metadata)
from app.db import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Create all tables once per test session, drop them afterwards."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _reset_igdb_token():
    """The IGDB provider caches its Twitch token module-globally; isolate tests."""
    from app.providers import igdb

    igdb._token["value"] = None
    igdb._token["expires"] = 0.0
    yield


@pytest.fixture(autouse=True)
def _reset_musicbrainz_throttle():
    """Forget the last MusicBrainz call, so its 1 req/s throttle never makes
    the suite sleep between tests."""
    from app.providers import musicbrainz

    musicbrainz._last_call["at"] = 0.0
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all tables between tests so each test starts clean."""
    yield
    from sqlalchemy import text

    with engine.begin() as conn:
        table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        if table_names:
            conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
