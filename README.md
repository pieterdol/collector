# Collector

Self-hosted tracker for your books, movies, TV shows and games — one shelf
for everything you own, play, read, watch and want. Built as an installable
PWA with a FastAPI backend, React frontend and PostgreSQL.

**Stack**: FastAPI · SQLAlchemy · Alembic · PostgreSQL (JSONB + full-text) ·
React 19 · TypeScript · Vite · TanStack Query · Tailwind v4 · nginx.

## Quick start

```bash
cp .env.example .env     # optional: add API keys (see below)
docker compose up --build
```

Then open **http://localhost:8080**, create an account — or seed demo data:

```bash
docker compose exec backend python -m app.seed
# login: demo@example.com / demo1234
```

> **Podman?** Works out of the box: `podman compose up --build`
> (needs `podman-compose`, e.g. `uv tool install podman-compose`).

## API keys (all optional)

The app runs without any key: books use Open Library (keyless) and every
type supports manual entry. Keys unlock movie/game search and Steam import.
Put them in `.env`:

| Key | Unlocks | Where to get it |
| --- | --- | --- |
| `TMDB_API_KEY` | Movie & TV search + metadata | [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) — free account, use the **v3 API key** |
| `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` | Game search + artwork via IGDB | [dev.twitch.tv/console/apps](https://dev.twitch.tv/console/apps) — register an app (any redirect URL) |
| `STEAM_API_KEY` | Steam library import | [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) — domain can be `localhost` |
| `JWT_SECRET` | Session token signing | `openssl rand -hex 32` — **set this in production** |

The Epic, GOG and PlayStation imports need no keys: Epic/GOG read a Heroic
or Legendary library file you upload, and PSN uses a pasted NPSSO token.

## Everyday commands

```bash
docker compose up -d              # start
docker compose logs -f backend    # follow API logs
docker compose exec backend pytest            # backend tests
docker compose exec backend alembic upgrade head   # run migrations manually
docker compose down               # stop (data persists in volumes)
docker compose down -v            # stop AND wipe database + covers
```

Migrations run automatically when the backend container starts. To create a
new migration after changing models:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
```

### Live-reload dev stack

Layer `docker-compose.dev.yml` on top for a hot-reloading backend (source
bind-mounted, `--reload`) plus pgAdmin on <http://localhost:5050>
(`admin@example.com` / `admin`):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

It re-runs `uv sync` on every start, so changing a dependency in
`backend/pyproject.toml` just needs another `up` — no rebuild and no
`down -v` to refresh the cached venv.

## Development without Docker

Backend (needs a Postgres; `podman run -d -e POSTGRES_PASSWORD=test -e POSTGRES_DB=collector_test -p 5433:5432 docker.io/library/postgres:16-alpine`):

```bash
cd backend
uv sync
uv run pytest                     # tests hit Postgres on :5433
uv run uvicorn app.main:app --reload   # API on :8000
```

Frontend (Vite dev server proxies /api and /media to :8000):

```bash
cd frontend
npm install
npm run dev                       # app on :5173
npm test                          # vitest
```

## Architecture

```
browser ──:8080──▶ frontend (nginx)
                    ├─ /        static React build (PWA: manifest + SW)
                    ├─ /api/*   ─▶ backend (FastAPI) ─▶ postgres
                    └─ /media/* ─▶ backend (cover images, media volume)
```

- **One origin** — nginx proxies the API, so no CORS and the service worker
  can cache covers.
- **Items** are user-owned rows with type-specific data in a JSONB
  `metadata` column; enum-ish fields are TEXT + CHECK constraints (enums
  live in code: `backend/app/domain/enums.py`, `frontend/src/lib/types.ts`).
- **Every mutation writes an `activity_events` row** in the same
  transaction (see `backend/app/core/events.py`). This append-only log plus
  `completed_at`/`acquisition_date` timestamps makes future dashboards
  (reads per year, hours over time, spend) pure queries — no backfill.
- **Metadata is fetched once**: external lookups cached 7 days in
  `provider_cache`; covers downloaded once to the media volume and served
  locally. Providers implement one interface
  (`backend/app/providers/base.py`) — add a source by subclassing and
  registering it.

## Features & flows

- **Add items** by catalog search (Open Library / TMDB / IGDB), by barcode,
  or manually. Missing keys degrade to manual entry with a hint.
- **Barcode scanning** uses the camera (native `BarcodeDetector`, falls
  back to `@zxing/browser`). ISBNs auto-fill books. Movie/game barcodes
  (UPC/EAN) have **no public catalog** — the code is stored on the item and
  the UI drops you into title search. There's also a type-the-digits
  fallback.
  *Camera access needs HTTPS or `localhost`.* The nicest setup is
  Tailscale on the server plus the Tailscale app on your phone:

  ```bash
  sudo tailscale set --operator=$USER    # once
  tailscale serve --bg http://localhost:8080
  ```

  Enable HTTPS certificates + Serve for the node when the CLI links you
  to the admin console (leave Funnel off unless you want the app on the
  public internet). You get https://<machine>.<tailnet>.ts.net with a
  valid certificate — full scanning + installable PWA from anywhere,
  visible only to your tailnet. Alternatives: `adb reverse tcp:8080
  tcp:8080` (Android, USB), or any HTTPS reverse proxy.
- **Library imports** live under *Import & settings* (sidebar footer /
  avatar menu). All of them skip already-imported games, so re-runs are
  safe, and covers arrive in the background:
  - **Steam** — SteamID64 or vanity name; playtime prefills progress.
    Steam "Game details" privacy must be public.
  - **Epic & GOG** — upload the library file a launcher already maintains:
    Heroic's store cache (`store_cache/legendary_library.json` /
    `gog_library.json`) or a `legendary list --json` dump. DLC and other
    runners are filtered out.
  - **PlayStation Network** — paste an NPSSO token (used once, never
    stored). Runs as a background job with live progress, then pauses for
    **review**: real games are preselected while PS Plus-gated claims,
    demos/betas/playtests, media apps and titles already in your library
    are auto-excluded (each with a reason, all rescuable). Games link to
    their console platform and import hours played; optional toggles
    include PS Plus games (marked) or skip PS4 twins of PS5 games.
- **Metadata enrichment**: storefront imports arrive without a catalog
  link, so the first detail-page visit matches games to IGDB by title and
  pulls description, hero art and screenshots. Wrong or missing match? The
  **Re-link** action on the detail page lets you pick the correct record —
  import provenance and playtime survive the swap.
- **Upcoming**: a release timeline of everything in your library or
  wishlist with a future release date, grouped by month, with countdown
  chips; partial dates ("2027", "09-2026") stay listed until their period
  ends.
- **TV seasons**: per-season ownership (with disc format) and
  watched-tracking on show pages; season data comes from TMDB.
- **Stats**: per-type tiles, continue-playing/reading, loans and recent
  activity — all read from the event log.
- **Wishlist** is first-class: no price/format until you hit **Acquire**,
  which records the acquisition and moves it to your backlog.
- **Loans**: lend to a name, mark returned — both logged.
- **Theming**: dark ("graphite", the designed theme) and a derived light variant,
  OS-aware with a persisted toggle. All colors are CSS custom properties in
  `frontend/src/styles/tokens.css`; a new theme is one more
  `[data-theme="…"]` block.
- **PWA**: add to home screen on iOS/Android; the app shell and covers are
  cached for quick loads.

## Project layout

```
backend/
  app/domain/enums.py    the enum single-source-of-truth
  app/models/            SQLAlchemy tables (users, items, item_seasons, platforms,
                         activity_events, provider_cache)
  app/api/               routers: auth, items, seasons, enrich, steam, epic, gog,
                         psn, stats, platforms
  app/core/              security (argon2+JWT), events, covers, artwork, seasons,
                         platforms, library_import, import_jobs
  app/providers/         MetadataProvider ABC + openlibrary/tmdb/igdb/steam/psn + cache
  app/tests/             pytest suite (runs against real Postgres)
  alembic/versions/      migrations
frontend/
  src/lib/               api client, TanStack Query hooks, types, dates, upcoming
  src/theme/             design tokens + theme store
  src/components/        PosterCard, ItemTable, BarcodeScanner, SeasonsPanel, …
  src/pages/             Shelf, Wishlist, Upcoming, Stats, AddItem, ItemDetail,
                         Settings, Login
```

## Out of scope (for now)

Richer dashboards (reads per year, hours over time, spend) beyond the
current stats tiles. The append-only event log and timestamps already
capture everything they'll need, so they remain pure queries — no
migration or backfill when they land.
