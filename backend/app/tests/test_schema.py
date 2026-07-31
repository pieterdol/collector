"""Schema-level tests: CHECK constraints, generated tsvector, cascades.

These run against the real Postgres schema created from the models; a
separate test proves the Alembic migration produces the same tables.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import ActivityEvent, Item, ProviderCache, User


def make_user(db, email="test@example.com"):
    user = User(email=email, password_hash="x", display_name="Test")
    db.add(user)
    db.commit()
    return user


def make_item(db, user, **overrides):
    fields = dict(
        user_id=user.id,
        type="book",
        format="physical",
        status="backlog",
        title="Dune",
        meta={"authors": ["Frank Herbert"]},
    )
    fields.update(overrides)
    item = Item(**fields)
    db.add(item)
    db.commit()
    return item


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def test_item_roundtrip_with_jsonb_metadata(db):
    user = make_user(db)
    item = make_item(db, user, meta={"authors": ["Frank Herbert"], "isbn": "978-0441172719"})
    fetched = db.get(Item, item.id)
    assert fetched.meta["isbn"] == "978-0441172719"
    assert fetched.created_at is not None
    assert fetched.updated_at is not None
    assert fetched.completed_at is None


def test_type_check_constraint_rejects_unknown_type(db):
    user = make_user(db)
    with pytest.raises(IntegrityError):
        make_item(db, user, type="vinyl")


def test_music_items_pass_the_type_check(db):
    user = make_user(db)
    item = make_item(
        db,
        user,
        type="music",
        title="Kid A",
        meta={"artist": "Radiohead", "media": 'Vinyl 12"'},
    )
    assert db.get(Item, item.id).meta["artist"] == "Radiohead"


def test_status_check_constraint_rejects_unknown_status(db):
    user = make_user(db)
    with pytest.raises(IntegrityError):
        make_item(db, user, status="paused")


def test_rating_check_allows_half_stars_only(db):
    user = make_user(db)
    make_item(db, user, rating=4.5)  # ok
    with pytest.raises(IntegrityError):
        make_item(db, user, title="Other", rating=4.3)


def test_rating_check_rejects_out_of_range(db):
    user = make_user(db)
    with pytest.raises(IntegrityError):
        make_item(db, user, rating=5.5)


def test_title_tsv_is_generated_and_searchable(db):
    user = make_user(db)
    make_item(db, user, title="The Name of the Wind")
    found = db.scalars(
        select(Item).where(text("title_tsv @@ plainto_tsquery('simple', 'wind')"))
    ).all()
    assert [i.title for i in found] == ["The Name of the Wind"]


def test_activity_events_cascade_on_item_delete(db):
    user = make_user(db)
    item = make_item(db, user)
    db.add(
        ActivityEvent(
            item_id=item.id,
            user_id=user.id,
            event_type="item_added",
            new_value={"status": "backlog"},
        )
    )
    db.commit()
    db.delete(item)
    db.commit()
    remaining = db.scalars(select(ActivityEvent)).all()
    assert remaining == []


def test_provider_cache_unique_per_provider_and_query(db):
    db.add(ProviderCache(provider="openlibrary", query_key="isbn:1", response={}))
    db.commit()
    db.add(ProviderCache(provider="tmdb", query_key="isbn:1", response={}))
    db.commit()  # same key, different provider: fine
    db.add(ProviderCache(provider="openlibrary", query_key="isbn:1", response={}))
    with pytest.raises(IntegrityError):
        db.commit()


def test_email_unique(db):
    make_user(db, "a@b.c")
    with pytest.raises(IntegrityError):
        make_user(db, "a@b.c")


def test_expected_indexes_exist(db):
    rows = db.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename IN ('items','activity_events')")
    ).scalars().all()
    for expected in [
        "ix_items_user_type_status",
        "ix_items_user_format",
        "ix_items_user_completed_at",
        "ix_items_title_tsv",
        "ix_items_user_bundle",
        "uq_items_bundle_front",
        "ix_activity_events_item_id",
        "ix_activity_events_user_created",
        "ix_activity_events_type_created",
    ]:
        assert expected in rows, f"missing index {expected}"


def test_only_one_copy_can_front_a_bundle(db):
    user = make_user(db)
    bundle_id = uuid.uuid4()
    make_item(db, user, bundle_id=bundle_id, bundle_front=True)
    with pytest.raises(IntegrityError):
        make_item(db, user, bundle_id=bundle_id, bundle_front=True)


def test_an_unbundled_item_cannot_front_a_bundle(db):
    user = make_user(db)
    with pytest.raises(IntegrityError):
        make_item(db, user, bundle_front=True)


def test_migration_produces_schema(tmp_path):
    """`alembic upgrade head` on a fresh database creates all tables."""
    import subprocess

    from app.config import get_settings

    url = get_settings().database_url
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    scratch = f"migrate_test_{uuid.uuid4().hex[:8]}"

    from sqlalchemy import create_engine

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{scratch}"'))
    try:
        scratch_url = url.rsplit("/", 1)[0] + f"/{scratch}"
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=str(__import__("pathlib").Path(__file__).parents[2]),
            env={**__import__("os").environ, "DATABASE_URL": scratch_url},
        )
        assert result.returncode == 0, result.stderr
        scratch_engine = create_engine(scratch_url)
        with scratch_engine.connect() as conn:
            tables = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).scalars().all()
            type_check = conn.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_items_type'"
                )
            ).scalar_one()
        scratch_engine.dispose()
        for t in ["users", "items", "activity_events", "provider_cache", "platforms",
                  "item_seasons", "item_episodes", "alembic_version"]:
            assert t in tables, f"missing table {t}"
        # Every ItemType must survive a real migration chain, not just
        # create_all — the CHECK is what the live DB enforces.
        for value in ["book", "movie", "tv", "game", "music"]:
            assert f"'{value}'" in type_check, f"{value} missing from {type_check}"
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{scratch}" WITH (FORCE)'))
        admin.dispose()
