# Collector — agent guide

Self-hosted media collection tracker (books/movies/TV/games). FastAPI +
SQLAlchemy + PostgreSQL backend, React 19 + TypeScript + Tailwind v4 PWA
frontend, docker-compose (works with podman). `README.md` holds the
user-facing docs; architecture rules live below.

## TDD — non-negotiable

Every behavior change starts with a failing test, then the implementation,
then the full suite green. No exceptions for "small" changes.

- Backend: add the test in `backend/app/tests/`, watch it fail, implement,
  re-run. External HTTP is always mocked with respx — tests never hit real
  APIs. Tests run against real Postgres (schema features matter here), and
  always against a derived `*_test` database, never the configured one.
- Frontend: logic and components get vitest coverage in
  `frontend/src/__tests__/` (api client, stores, key components). Pure
  styling changes don't need tests, but any behavior does.
- A feature is done when: new tests pass, the FULL suite passes, the
  compose stack still boots, and `README.md` reflects it (features,
  API keys, project layout — whatever the change touches).

## Commands

```bash
# backend (needs Postgres on :5433 — see README "Development without Docker")
cd backend && uv run pytest                  # full suite
cd backend && uv run pytest app/tests/test_x.py -k name   # one test

# frontend (no node on host — use the container)
cd frontend && podman run --rm -v "$PWD:/app:Z" -w /app docker.io/library/node:22-alpine \
  sh -c "npm run build && npm test"

# full stack
docker compose up -d --build                 # podman compose works too
docker compose exec backend pytest           # suite inside the container
docker compose exec backend alembic revision --autogenerate -m "..."
```

## Architecture rules (violating these breaks future features)

- **Enums live in code, not the DB**: TEXT + CHECK constraints; the single
  sources of truth are `backend/app/domain/enums.py` and
  `frontend/src/lib/types.ts`. Adding a value = both files + a migration
  replacing the CHECK.
- **Every item mutation writes an `activity_events` row in the same
  transaction** (`backend/app/core/events.py`). The log is append-only —
  never update or repurpose rows (the only exception: the user-facing
  per-event DELETE endpoint). Future dashboards depend on it.
- **Fetch-once**: external lookups go through `provider_cache`
  (`app/providers/cache.py`); images are downloaded once into the media
  volume (`core/covers.py`, `core/artwork.py`) — never hotlink.
- **Metadata providers** implement `app/providers/base.py` and are
  registered in `app/providers/__init__.py`. One type may be served by two
  catalogs: `providers/music.py` fronts MusicBrainz (keyless default) and
  Discogs (`DISCOGS_TOKEN`), which is why music `external_id`s are
  namespaced (`mb:<uuid>` / `discogs:<id>`) — `details`/relink route on that
  prefix, never on what happens to be configured. Both mappers must emit
  the same metadata keys.
- **Platforms are records** (`platforms` table, synced once from IGDB);
  games link via `items.platform_id`. Link by name through
  `core/platforms.find_or_create_platform` — never write bare strings only.
- **Theming is token-only**: all colors are CSS custom properties in
  `frontend/src/styles/tokens.css`; components reference semantic tokens
  (`var(--accent)`, `bg-surface`), never raw hex. Every visual change must
  work in dark AND light.
- **Schema changes** always ship as an Alembic migration (auto-run on
  backend start) plus, when data exists, a backfill in the same migration.
- Keep files small and single-purpose; match the existing patterns.
