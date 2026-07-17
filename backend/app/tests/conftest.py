"""Shared test fixtures.

Tests run against a real PostgreSQL (JSONB, tsvector and CHECK constraints
are part of what we're testing). Locally: `make test-db` starts one on :5433.
In the container: compose's db service is used.
"""

import os

# Test database must be configured before app modules create the engine.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:test@localhost:5433/collector_test",
)
os.environ.setdefault("MEDIA_DIR", "/tmp/collector-test-media")

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
