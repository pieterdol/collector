# Collector — personal media collection tracker (PWA)

## Context

Greenfield build in the empty repo `collector`. A self-hosted web app to track a personal collection of Books, Movies (DVD/Blu-ray), and Games — prototype-scale but architecturally sound. Monorepo, fully containerized, runs with `docker compose up` (via podman on this host). Dashboards are explicitly out of scope, but the schema must make future stats possible with **no migration or backfill** (append-only event log + timestamps).

### Decisions agreed with the user (supersede the original prompt where they differ)
1. **No household — items are user-owned.** Each item belongs to one user (`items.user_id`). Status/progress/rating/review live directly on the `items` row. `activity_events.user_id` is kept so sharing could be added later without touching event history.
2. **Fetch metadata once**: cover images downloaded at add time into a local media volume, served by the backend (never hotlinked); external lookups cached in a `provider_cache` table (TTL). Item metadata is a per-item JSONB snapshot.
3. **Barcode scope**: full ISBN → Open Library flow for books. No UPC→TMDB/IGDB lookup exists; scanner captures UPC into metadata, fill falls back to title search.
4. **Auth**: email+password, argon2, JWT bearer in localStorage. No OAuth.
5. **Host tooling**: Fedora Atomic (no Docker installable). Podman 5.8.2 + rootless socket active. Install `podman-compose` via `uv tool install` + `docker`→`podman` shim in `~/.local/bin`. Compose file stays 100% standard.
6. **No DB enum types** — Postgres native enums share MySQL's pain (can't remove/reorder values, DDL to add). All enum-like columns are `TEXT` + `CHECK` constraint, with the real enum defined once in code (Python `enum.Enum` / TS union types). CHECK constraints are trivially replaced in a migration.
7. **TDD throughout the backend** — tests written before/with each feature (auth, CRUD, events, filters/search, providers, covers, Steam import), red→green per slice. Frontend: vitest for lib/logic (api client, query helpers, barcode parsing, theme store) + a few component tests; visual polish iterated manually.
8. **Wishlist is a first-class flow**, not just a status value: dedicated view/tab, wishlist items carry no purchase/acquisition data yet, and a "Mark as acquired" action prompts for price/format/date, flips status to `backlog`, stamps `acquisition_date`, and records an `acquired` activity event.
9. **Theme system from day one**: all colors/spacing/type as CSS custom properties (design tokens); themes = token sets. Ships with dark (default) + light, honors `prefers-color-scheme`, persisted toggle, and adding future themes = one CSS block, no component changes.
10. **Design-first**: before building the frontend, produce interactive HTML mockups (published as an Artifact) following the `/frontend-design` skill's process, showing palette, type scale, collection gallery + table, item detail, add flow, and the theme toggle — user approves/adjusts before implementation.
11. **`PLAN.md` lives in the repo** — this plan is written to `collector/PLAN.md` as step 0 and kept current as decisions evolve.

## Environment facts (verified)
- Podman 5.8.2, rootless socket at `/run/user/1000/podman/podman.sock`; no docker, no node/npm on host
- `uv 0.11.28` available; 732 GB free; `/usr` read-only (atomic host)

## Architecture

Single-origin serving (no CORS, clean PWA service worker):

```
browser ── :8080 ──> frontend container (nginx)
                       ├── /            → built React app (static)
                       ├── /api/*       → proxy → backend:8000
                       └── /media/*     → proxy → backend:8000 (covers)
backend (FastAPI/uvicorn) ──> postgres:5432
volumes: pgdata, media (cover images)
```

## Data model (PostgreSQL, all timestamps timestamptz, NO native enums)

**users** — `id UUID PK, email CITEXT UNIQUE, password_hash TEXT (argon2), display_name TEXT, created_at`

**items** — user-owned entry:
- `id UUID PK, user_id UUID FK→users`
- `type TEXT CHECK IN ('book','movie','game')`
- `format TEXT CHECK IN ('physical','digital')` — nullable while status='wishlist' (may not know yet)
- `status TEXT CHECK IN ('wishlist','backlog','in_progress','completed','abandoned')`
- `title TEXT NOT NULL`, `cover_path TEXT` (local; source URL in metadata)
- `metadata JSONB NOT NULL DEFAULT '{}'` — book(authors, isbn, page_count, publisher) / movie(director, year, runtime, tmdb_id) / game(platform, developer, playtime_minutes, igdb_id, steam_appid); plus `upc`, `cover_source_url`
- `progress_current NUMERIC`, `progress_total NUMERIC` (pages / hours; NULL for movies)
- `rating NUMERIC(2,1) CHECK (rating BETWEEN 0 AND 5 AND rating*2 = floor(rating*2))`, `review TEXT`
- `purchase_price NUMERIC(10,2)`, `currency CHAR(3)`, `acquisition_date DATE` — NULL while wishlist
- loan: `borrowed_by TEXT`, `loaned_date DATE`, `returned_date DATE`
- `created_at, updated_at, completed_at` (set when status enters `completed`)
- `title_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', title)) STORED`

**activity_events** — append-only:
- `id UUID PK, item_id UUID FK ON DELETE CASCADE, user_id UUID FK`
- `event_type TEXT` (`item_added | status_change | progress_update | rating_set | acquired | loan_out | loan_return | item_deleted`)
- `old_value JSONB, new_value JSONB, created_at`

**provider_cache** — `(provider, query_key) UNIQUE, response JSONB, fetched_at, expires_at`

**Indexes**: items `(user_id, type, status)`, `(user_id, format)`, partial `(user_id, completed_at) WHERE completed_at IS NOT NULL`, GIN `(title_tsv)`; events `(item_id)`, `(user_id, created_at)`, `(event_type, created_at)`.

Event writing centralized in `app/core/events.py`; every mutation records events in the same transaction.

## Folder structure

```
collector/
├── PLAN.md                       # this plan, kept current
├── docker-compose.yml            # postgres + backend + frontend(nginx)
├── .env.example                  # all keys documented
├── README.md
├── backend/
│   ├── Dockerfile                # python:3.12-slim + uv
│   ├── pyproject.toml
│   ├── alembic.ini / alembic/versions/0001_initial.py
│   └── app/
│       ├── main.py  config.py  db.py
│       ├── models/               # user, item, activity_event, provider_cache
│       ├── domain/enums.py       # ItemType/ItemFormat/ItemStatus/EventType (single source of truth)
│       ├── schemas/              # pydantic: auth, item, enrich, steam
│       ├── api/                  # routers: auth, items, enrich, steam
│       ├── core/                 # security.py, events.py, covers.py
│       ├── providers/            # base.py ABC, openlibrary, tmdb, igdb, steam, cache.py
│       ├── seed.py
│       └── tests/                # TDD: test_auth, test_items_crud, test_events,
│                                 # test_filters_search, test_wishlist_acquire,
│                                 # test_providers (respx-mocked), test_steam_import
└── frontend/
    ├── Dockerfile  nginx.conf  package.json  vite.config.ts  index.html
    └── src/
        ├── lib/                  # api.ts, queries.ts, types.ts (TS unions mirror domain/enums)
        ├── theme/                # tokens.css (custom properties per theme), useTheme.ts
        ├── components/           # ItemCard, ItemTable, FilterBar, RatingStars, BarcodeScanner,
        │                         # ProgressEditor, AcquireDialog, Skeletons, EmptyState, ThemeToggle
        ├── pages/                # Login, Register, Collection, Wishlist, ItemDetail, AddItem, SteamImport
        └── __tests__/            # vitest: api client, theme store, barcode parse, key components
```

## API surface (/api)
- `POST /auth/register`, `POST /auth/login` → JWT; `GET /auth/me`
- `GET /items` (type/format/status filters, `q` full-text, sort, pagination) · `POST /items` · `GET/PATCH/DELETE /items/{id}`
- `POST /items/{id}/acquire` {price?, currency?, format, acquisition_date} — wishlist→backlog + event
- `GET /enrich/search?type=&q=` · `GET /enrich/barcode?code=`
- `POST /steam/import` {steam_id_or_vanity} — resolve vanity, fetch owned games, dedupe on `metadata.steam_appid`, bulk-create digital games with playtime
- Backend serves `/media/covers/*`

## Providers
`MetadataProvider` ABC: `search(query)`, `lookup_barcode(code)`; implementations OpenLibrary (keyless), TMDB (`TMDB_API_KEY`), IGDB (`TWITCH_CLIENT_ID/SECRET`), Steam (`STEAM_API_KEY`). All through `provider_cache` (~7-day TTL). Missing key ⇒ `available=False` ⇒ UI degrades to manual entry. `core/covers.py` downloads cover once at creation (size cap, content-type check) → `media/covers/{item_id}.jpg`.

## Design direction — v3 "Graphite" (CURRENT, from user's Claude Design file)
Ported 18 Jul 2026 from `~/Downloads/Collector.html` (Media Tracker Dashboard). Supersedes v2 below.
- **Palette (dark, designed)**: bg `#111114`, surface `#1b1b20`, raised `#2a2a31`, text `#ececf1`, muted `#9a9aa6`; accent `oklch(76% 0.14 290)` with DARK ink on buttons; medium colors book `oklch(80% .12 75)` amber / movie `oklch(80% .12 350)` rose / game `oklch(80% .12 230)` blue (captions, badges, progress bars — never chrome on art). Light variant derived (design was dark-only). Tokens in `frontend/src/styles/tokens.css`.
- **Type**: Space Grotesk (display), IBM Plex Sans (UI), IBM Plex Mono (data). Radii: cards 14 / covers 10 / buttons 9 / chips 999.
- **Layout**: 232px labeled sidebar (nav dots; theme+account at bottom; bottom tab bar on mobile) + page header (title, search, Gallery/Table, Scan, + Add item). Library: type chips (active inverts to text-on-bg), status+sort dropdowns, loan banner, flat poster cards with status badge on art. Detail: 240px key-art hero + overlapping cover, About/Screenshots/Review/Activity left, Progress/Details/Loan/Danger right. Stats page: 4 tiles + Continue/Out on loan/Recent activity.
- **New backend for v3**: `/api/stats` (pure queries over events/timestamps) and `POST /items/{id}/artwork` — hero/screenshots/description fetched once (Steam appdetails keyless → IGDB → TMDB backdrops), stored in media volume + item metadata, lazily triggered on first detail view.

## Design direction — "Midnight shelf" v2 (superseded — Stremio-inspired, flat & modern)
Reference: user's Stremio screenshot (flat posters, deep indigo night palette). Mockup approved 17 Jul 2026:
https://claude.ai/code/artifact/0e26b268-8ffd-4d02-bb3b-f853fb8e6302 (source: scratchpad mockup.html — port its tokens/CSS to the frontend).
- **Palette (dark default)**: bg `midnight #0F0D20`, rail `#0B0A18`, panel `#191631`, raised `#232048`, text `#F1F0F7`, muted `#918DAE`. Accent `iris #7263F2` = ALL interactive states (active nav/pills, hover ring, buttons). `signal green #21C179` = progress strips, completed, acquire-confirm. Medium dots (captions/filters only, never chrome on posters): book `amber #DFA14E`, movie `rose #E8637C`, game `mint #4EC9A4`. Light theme "daybreak": bg `#F4F3FA`, white panels, accent `#5B4BE0`. Themes = token sets only.
- **Type**: Plus Jakarta Sans for ALL UI (800 display, 700 headings, 400 body); Spline Sans Mono for data (ISBN, counts, dates, eyebrows). Self-hosted.
- **Layout**: left icon rail (logo, shelf, wishlist, add) → becomes bottom tab bar on mobile; centered pill search; filter pills (solid accent when active); poster grid = flat cover-only cards (rounded 12px, no chrome) + one-line caption (title + medium dot + format/stars). Progress = thin green strip on poster bottom edge; status/loan = small translucent badges on the art. Dense table view kept.
- **Item detail = separate full page** (user request, better on mobile): back pill → blurred cover-color glow backdrop, large poster + display title, mono meta row, metadata chips, flat panels: progress (green bar + stepper), rating (half-stars) + review, loan, activity timeline.
- **Wishlist**: dashed accent border + dimmed poster, Acquire button on hover/tap, acquire dialog (price/currency/format/date) → backlog.

## Frontend key points
- **Theming**: `src/theme/tokens.css` defines semantic tokens (`--bg`, `--surface`, `--text`, `--accent`, type scale, radii) per `[data-theme]`; Tailwind consumes tokens via CSS vars. Dark default, light included, system-pref + persisted toggle.
- **PWA**: vite-plugin-pwa manifest + SW (precache shell, runtime-cache covers).
- **Barcode**: native `BarcodeDetector` → `@zxing/browser` fallback; rear camera; mobile-first.
- **Views**: Collection (cover-dominant grid + dense table toggle, filter chips, sort, debounced search), Wishlist tab with AcquireDialog, ItemDetail (progress, half-star rating, loans), AddItem (search-first → barcode → manual), Steam import wizard. Skeletons, empty states, micro-interactions.

## Build order (TDD: tests first per backend slice)
0. Write `PLAN.md` to repo. Host tooling: `uv tool install podman-compose` + docker shim.
1. **Design mockups** (HTML Artifact): palette/type tokens, collection gallery + table, item detail, add flow, wishlist, theme toggle. **Pause for user approval.**
2. Scaffold monorepo: compose, Dockerfiles, .env.example, pyproject, Vite app; pytest runs green in container.
3. Schema: models + Alembic 0001 (TEXT+CHECK, tsvector via raw DDL) — migration test.
4. Auth TDD → items CRUD + events TDD → filters/full-text TDD → wishlist/acquire TDD.
5. Providers + cache + covers TDD (respx mocks) → enrich endpoints.
6. Steam import TDD.
7. Frontend: theme system → auth pages → collection views → detail → add flows (incl. scanner) → wishlist → Steam import → PWA + polish (matching approved mockups).
8. Seed script (demo users + ~15 items, offline-graceful). README.

## Verification
- `docker compose up --build` (shim/podman) → services healthy, migrations auto-run, seed via exec
- `docker compose exec backend pytest` — full TDD suite green; frontend `vitest` green in build
- curl smoke: register→login→CRUD→acquire; psql check `activity_events` + `completed_at`
- Browser: demo login, gallery/table, filters/search, add via title search, wishlist→acquire, theme toggle, PWA installable (manifest+SW)
- Barcode: manual test steps in README (camera + localhost/HTTPS required)
