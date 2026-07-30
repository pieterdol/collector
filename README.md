# Collector

Self-hosted tracker for your books, records, movies, TV shows and games —
one shelf for everything you own, play, read, watch and want. Built as an
installable PWA with a FastAPI backend, React frontend and PostgreSQL.

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

The app runs without any key: books use Open Library and music uses
MusicBrainz (both keyless), and every type supports manual entry. Keys
unlock movie/game search and Steam import. Put them in `.env`:

| Key | Unlocks | Where to get it |
| --- | --- | --- |
| `TMDB_API_KEY` | Movie & TV search + metadata | [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) — free account, use the **v3 API key** |
| `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` | Game search + artwork via IGDB | [dev.twitch.tv/console/apps](https://dev.twitch.tv/console/apps) — register an app (any redirect URL) |
| `STEAM_API_KEY` | Steam library import | [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) — domain can be `localhost` |
| `DISCOGS_TOKEN` | Deeper music search (Discogs instead of MusicBrainz) | [discogs.com/settings/developers](https://www.discogs.com/settings/developers) — "Generate new token" |
| `JWT_SECRET` | Session token signing | `openssl rand -hex 32` — **set this in production** |

The Epic, GOG and PlayStation imports need no keys: Epic/GOG read a Heroic
or Legendary library file you upload, and PSN uses a pasted NPSSO token.

**Reading a photographed cover** needs no key either, but it does need a
local [Ollama](https://ollama.com) — no data ever leaves your machine:

```bash
ollama pull qwen3-vl:4b && ollama pull moondream
```

| Setting | Default | What it does |
| --- | --- | --- |
| `OLLAMA_URL` | *(empty — feature off)* | e.g. `http://host.containers.internal:11434` from the container, `http://localhost:11434` on the host |
| `VISION_MODEL` | `qwen3-vl:4b` | Reads the printed title (3–5 s per photo). The 8b is ~7× slower and no more accurate on box art |
| `VISION_RECOGNIZER_MODEL` | `moondream` | Second opinion that recognises covers it knows; empty to run the reader alone |

Ollama listens on `127.0.0.1` by default, which a container cannot reach.
Either run it with `OLLAMA_HOST=0.0.0.0:11434`, or point `OLLAMA_URL` at
wherever it actually listens.

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

- **Add items** by catalog search (Open Library / TMDB / IGDB /
  MusicBrainz or Discogs), by barcode, or manually. Missing keys degrade to manual entry with a hint. Game
  search takes a **platform filter** (only games released on it come back,
  and it's preselected as the platform you file the copy under), and the
  search term and filter survive stepping into the confirm form and back
  via *← results*. Half-typed titles work: IGDB's search index only
  matches whole words, so "sekir" would find nothing — a query that comes
  back empty is retried as a name-contains lookup, most-rated first.
- **Library search** covers titles (Postgres full-text plus substring), the
  people behind an item — authors, artists, directors, studios — and
  synopses. So "batman" finds *Batman Begins* and *The Dark Knight*, and
  "radiohead" or "herbert" finds everything by them. Results are tiered:
  title matches, then creator matches, then description-only ones,
  whatever sort is active. The box clears with the **×** at its right edge
  (or Esc), which drops `?q=` and keeps every other filter.
- **Barcode scanning** uses the camera (native `BarcodeDetector`, falls
  back to `@zxing/browser`). ISBNs auto-fill books, and sleeve barcodes
  (UPC/EAN) auto-fill records — the music catalogs index them, and a match
  picks the medium for you. Movie and game barcodes have **no public
  catalog**: the code is stored on the item and the UI drops you into title
  search. There's also a type-the-digits fallback.
  Scanning something you **already added** opens that item with *You already
  own this item* (or *…already on your wishlist*) instead of starting a
  duplicate — matched against the ISBN/UPC/sleeve barcode stored on your
  items, in either ISBN form, and it skips the catalog call entirely.
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
- **Photo of the cover** (needs a local Ollama — see *API keys*): the answer
  for discs and game boxes, which no public barcode catalog covers. Snap the
  front and a vision model reads the title, which becomes an ordinary catalog
  search — you still pick the match, so a partial read costs nothing. Two
  models are asked because they fail in opposite directions: `qwen3-vl:4b`
  does real OCR and drops what it can't make out (a cursive *Stellar* Blade
  reads as just "BLADE"), while `moondream` recognises covers it knows from
  the art alone and invents titles when it doesn't. Every answer is only a
  search term, and the catalog is what decides which one was real. Photos are
  downscaled to 1024px and uprighted first (EXIF rotation ruins the read),
  in the browser and again server-side. Nothing matched? The read text is
  still in the search box, one word away from right.
- **Library imports** live under *Import & settings* (sidebar footer /
  avatar menu). All of them skip already-imported games, so re-runs are
  safe, and covers arrive in the background:
  - **Steam** — SteamID64 or vanity name; playtime prefills progress.
    Steam "Game details" privacy must be public.
  - **Epic & GOG** — upload the library file a launcher already maintains:
    Heroic's store cache (`store_cache/legendary_library.json` /
    `gog_library.json`, also under
    `~/.var/app/com.heroicgameslauncher.hgl/config/heroic/` for the
    Flatpak) or a `legendary list --json` dump. DLC and other runners are
    dropped outright.
  - **PlayStation Network** — paste an NPSSO token (used once, never
    stored). Games link to their console platform (PS5, PS4, …) and import
    hours played; optional toggles include PS Plus games (marked) or skip
    PS4 twins of PS5 games.

  Epic, GOG and PSN imports run as background jobs with live progress and
  pause for **review** before anything is created: real games come
  preselected, while non-games (companion apps, demos/betas/playtests,
  media apps, launcher redistributables), PS Plus-gated claims and titles
  already in your collection are auto-excluded — each with its reason, in
  a collapsed list, all rescuable with a checkbox.
- **Metadata enrichment**: storefront imports arrive without a catalog
  link, so the first detail-page visit matches games to IGDB by title and
  pulls description, hero art and screenshots. Wrong or missing match? The
  **Re-link** action on the detail page lets you pick the correct record —
  import provenance and playtime survive the swap.
- **Fields you can fix by hand**: the detail page edits things in place —
  tap the **title** to rename an item (Escape abandons, an emptied field
  reverts), and in Details: disc media, storefront, a release date that is
  still unknown, and the **author** of a book. Open Library leaves the author
  out for plenty of editions (and a manual add can be saved without one), and
  books have no Re-link, so the Author row is tap-to-type: one name, or
  several separated by commas. Clearing it empties the field again.
- **Music, pressing by pressing**: records are tracked as the copy you own,
  not just the album. Search returns *releases* — artist, year, carrier,
  label, catalogue number, country — because that's what tells a 2000 UK
  2×LP from a later reissue. Picking one stores the tracklist (with side
  labels: A1, A2, …), which the detail page lists, and the carrier
  (Vinyl LP / 12" / 10" / 7" / CD / Cassette) becomes a filterable badge on
  the poster. Sleeve art comes from the Cover Art Archive or Discogs and is
  downloaded once like every other cover.
  MusicBrainz is the default and needs no key; `DISCOGS_TOKEN` switches
  search to Discogs, which knows more about physical pressings. Either way
  the stored `external_id` says which catalogue matched (`mb:…` /
  `discogs:…`), so re-linking keeps working after you add the token.
- **Upcoming**: a release timeline of everything in your library or
  wishlist with a future release date, grouped by month, with countdown
  chips; partial dates ("2027", "09-2026") stay listed until their period
  ends.
- **TV seasons & episodes**: show pages list their seasons as a compact
  accordion — poster thumbnail, air year, episode count, watch progress.
  Open one for its ownership (with disc format), the whole-season watched
  control and a per-episode checklist. Episode lists come from TMDB the
  first time a season is opened (never at add time), and watch state syncs
  both ways: ticking the last episode marks the season watched, marking the
  season ticks every episode. **Refresh** re-checks TMDB for a running
  show's new episodes.
- **Stats**: per-type tiles, continue-playing/reading, loans and recent
  activity — all read from the event log.
- **Wishlist** is first-class: no price/format until you hit **Acquire**,
  which records the acquisition and moves it to your backlog. On desktop that
  button appears over the poster on hover; on narrow screens the poster stays
  uncovered and you acquire from the item page ("Mark as owned").
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
  app/models/            SQLAlchemy tables (users, items, item_seasons,
                         item_episodes, platforms, activity_events, provider_cache)
  app/api/               routers: auth, items, seasons, episodes, enrich, steam,
                         epic, gog, psn, stats, platforms (epic/gog share
                         store_import)
  app/core/              security (argon2+JWT), events, covers, artwork, seasons,
                         episodes, platforms, barcodes, vision (cover OCR),
                         library_import, import_jobs, store_filters
  app/providers/         MetadataProvider ABC + openlibrary/tmdb/igdb/steam/psn +
                         music (musicbrainz/discogs behind one front) + formats + cache
  app/tests/             pytest suite (runs against real Postgres)
  alembic/versions/      migrations
frontend/
  src/lib/               api client, TanStack Query hooks, types, dates, upcoming,
                         music, images (photo downscaling)
  src/theme/             design tokens + theme store
  src/components/        PosterCard, ItemTable, BarcodeScanner, SeasonsPanel,
                         SearchBox, …
  src/pages/             Shelf, Wishlist, Upcoming, Stats, AddItem, ItemDetail,
                         Settings, Login
```

## Out of scope (for now)

Richer dashboards (reads per year, hours over time, spend) beyond the
current stats tiles. The append-only event log and timestamps already
capture everything they'll need, so they remain pure queries — no
migration or backfill when they land.

## Data sources & attribution

- **TMDB** — movie & TV metadata and images.
  This product uses the [TMDB](https://www.themoviedb.org) API but is not
  endorsed or certified by TMDB.
- **IGDB** — game metadata and artwork, via [IGDB.com](https://www.igdb.com)
  (a Twitch service).
- **Open Library** — book metadata and covers, from
  [Open Library](https://openlibrary.org) (an Internet Archive project).
- **MusicBrainz & the Cover Art Archive** — music metadata and sleeve art,
  from [MusicBrainz](https://musicbrainz.org) and the
  [Cover Art Archive](https://coverartarchive.org) (MetaBrainz Foundation).
  Used keyless, within their rate limit (1 request/second) and with an
  identifying User-Agent, as their API terms ask.
- **Discogs** — music release data and images, from
  [Discogs](https://www.discogs.com), when a token is configured. This
  project is not affiliated with or endorsed by Discogs.
- **Steam / PlayStation Network** — library imports use the Steam Web API
  and PSN. This project is not affiliated with Valve or Sony.
- **Heroic & Legendary** — Epic and GOG imports read the library files
  maintained by the open-source
  [Heroic Games Launcher](https://heroicgameslauncher.com) and
  [Legendary](https://github.com/derrod/legendary). This project is not
  affiliated with them, Epic Games or GOG.

Cover art and posters shown in the app (and in screenshots) remain the
property of their respective rights holders. The MIT license covers this
project's code only, not third-party metadata or imagery.
