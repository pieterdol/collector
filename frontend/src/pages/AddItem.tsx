/** Add flow: pick a medium, then search a catalog / scan a barcode /
 * enter manually. Search and scan prefill the same confirm form. */

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { BarcodeScanner } from "../components/BarcodeScanner";
import { SearchIcon } from "../components/icons";
import {
  useBarcodeLookup,
  useCreateItem,
  useEnrichDetails,
  useEnrichSearch,
  usePhotoRead,
  usePlatformCatalog,
  useProviders,
} from "../lib/queries";
import type { EnrichResult, ItemStatus, ItemType, PhotoRead } from "../lib/types";
import { mediaOptions } from "../lib/types";

/** Fallback catalog name per type, for before /providers has answered. */
const PROVIDER_LABEL: Record<ItemType, string> = {
  book: "Open Library",
  movie: "TMDB",
  tv: "TMDB",
  game: "IGDB",
  music: "MusicBrainz",
};

/** Display name per provider, so music can say which catalog is actually
 * in use — MusicBrainz by default, Discogs once its token is configured. */
const PROVIDER_NAME_LABEL: Record<string, string> = {
  openlibrary: "Open Library",
  tmdb: "TMDB",
  igdb: "IGDB",
  musicbrainz: "MusicBrainz",
  discogs: "Discogs",
};

type Mode = "search" | "scan" | "photo" | "manual";

const MODE_LABEL: Record<Mode, string> = {
  search: "Search",
  scan: "Scan barcode",
  photo: "Photo of cover",
  manual: "Manual entry",
};

// Long enough that the pauses in ordinary typing don't each fire a search
// (300ms did, which made the search feel like it ran on every keystroke).
const SEARCH_DEBOUNCE_MS = 450;

const STOREFRONTS = [
  "Steam",
  "Epic Games Store",
  "GOG",
  "Xbox App / Game Pass",
  "EA App",
  "Ubisoft Connect",
  "Battle.net",
  "itch.io",
  "PlayStation Store",
  "Nintendo eShop",
];

// Shown first in the platform dropdown; the full IGDB catalog follows.
const COMMON_PLATFORMS = [
  "PC (Microsoft Windows)",
  "PC (Steam)",
  "Nintendo Switch",
  "Nintendo Switch 2",
  "PlayStation 5",
  "PlayStation 4",
  "Xbox Series X|S",
  "Xbox One",
];

export default function AddItem() {
  const [searchParams] = useSearchParams();
  const initialMode = searchParams.get("mode") === "scan" ? "scan" : "search";
  const [type, setType] = useState<ItemType>("book");
  const [mode, setMode] = useState<Mode>(initialMode);
  const [draft, setDraft] = useState<EnrichResult | null>(null);
  const [scannedUpc, setScannedUpc] = useState<string | null>(null);
  // Search term and game platform filter live here, not in SearchMode:
  // stepping into the confirm form and back must not lose them.
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("");
  const providers = useProviders();

  const available = useMemo(() => {
    const map: Partial<Record<ItemType, boolean>> = {};
    for (const p of providers.data?.providers ?? []) map[p.type] = p.available;
    return map;
  }, [providers.data]);

  const labels = useMemo(() => {
    const map = { ...PROVIDER_LABEL };
    for (const p of providers.data?.providers ?? []) {
      if (PROVIDER_NAME_LABEL[p.name]) map[p.type] = PROVIDER_NAME_LABEL[p.name];
    }
    return map;
  }, [providers.data]);

  // Books have ISBNs, records have sleeve barcodes; nothing else is in a
  // public barcode catalog.
  const scannable = type === "book" || type === "music";
  // Reading the cover needs a vision backend configured server-side (a local
  // Ollama, Gemini, …); with none the tab would only ever error, so it hides.
  const canRead = providers.data?.vision ?? false;
  const modes: Mode[] = [
    "search",
    ...(scannable ? (["scan"] as Mode[]) : []),
    ...(canRead ? (["photo"] as Mode[]) : []),
    "manual",
  ];
  // What the models read off the last photo — shown next to the search box,
  // because a wrong read has to be visible to be correctable.
  const [photoRead, setPhotoRead] = useState<string[]>([]);

  // w-full matters: without it, a flex-column item with mx-auto shrink-wraps
  // to its content's intrinsic width, and long unbreakable result lines
  // (game platform lists) push the page past the viewport on mobile.
  return (
    <section className="mx-auto w-full max-w-[640px]">
      <h2 className="m-0 mb-1 text-[26px] font-extrabold tracking-tight">Add to collection</h2>
      <p className="m-0 mb-6 text-[14.5px] text-muted">
        Search a catalog, scan a barcode, or enter it yourself.
      </p>

      <div className="mb-5 grid grid-cols-5 gap-2.5 max-[560px]:grid-cols-3">
        {(Object.keys(PROVIDER_LABEL) as ItemType[]).map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={type === t}
            onClick={() => {
              setType(t);
              setDraft(null);
              if (t !== "book" && t !== "music" && mode === "scan") setMode("search");
            }}
            className={`flex flex-col items-center gap-1 rounded-xl border px-2.5 py-3.5 transition-colors ${
              type === t
                ? "border-accent bg-accent/10"
                : "border-transparent bg-surface hover:bg-raised"
            }`}
          >
            <b className="text-sm font-bold capitalize text-text">{t}</b>
            <small
              className={`font-mono text-[9.5px] uppercase tracking-[0.1em] ${type === t ? "text-accent" : "text-faint"}`}
            >
              {labels[t]}
            </small>
          </button>
        ))}
      </div>

      {draft ? (
        <ConfirmForm
          type={type}
          label={labels[type]}
          draft={draft}
          scannedUpc={scannedUpc}
          preferredPlatform={type === "game" ? platform : ""}
          onBack={() => setDraft(null)}
        />
      ) : (
        <>
          <div className="mb-5 flex w-fit flex-wrap gap-1.5 rounded-[10px] border border-line bg-surface p-1" role="tablist">
            {modes.map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={`rounded-[8px] px-4 py-1.5 text-[13px] font-semibold transition-colors ${
                  mode === m ? "bg-raised text-text" : "text-muted hover:text-text"
                }`}
              >
                {MODE_LABEL[m]}
              </button>
            ))}
          </div>

          {mode === "search" && (
            <SearchMode
              type={type}
              label={labels[type]}
              available={available[type] ?? false}
              query={query}
              onQuery={setQuery}
              platform={platform}
              onPlatform={setPlatform}
              onPick={(result) => {
                setScannedUpc(null);
                setDraft(result);
              }}
            />
          )}
          {mode === "scan" && (
            <ScanMode
              onMatch={(result) => {
                setScannedUpc(null);
                // A scanned code decides the medium: an ISBN is a book, a
                // sleeve barcode is a record.
                setType(result.type);
                setDraft(result);
              }}
              onUpc={(code) => {
                setScannedUpc(code);
                setMode("search");
              }}
            />
          )}
          {mode === "photo" && (
            <PhotoMode
              type={type}
              onRead={(read) => {
                // The catalog-confirmed candidate, or the best guess so the
                // box starts from a near-miss instead of empty.
                setQuery(read.query ?? read.read[0] ?? "");
                setPhotoRead(read.read);
                if (read.platform && type === "game") setPlatform(read.platform);
                setMode("search");
              }}
            />
          )}
          {mode === "manual" && (
            <ConfirmForm
              type={type}
              label={labels[type]}
              draft={null}
              scannedUpc={scannedUpc}
              preferredPlatform={type === "game" ? platform : ""}
            />
          )}

          {photoRead.length > 0 && mode === "search" && (
            <p className="mt-4 rounded-lg bg-surface px-4 py-3 text-[13px] text-muted">
              Read from the cover: <b>{photoRead.join(" · ")}</b>. Stylised titles come back
              partial — fix the search above if that isn't it.
            </p>
          )}

          {scannedUpc && mode === "search" && (
            <p className="mt-4 rounded-lg bg-surface px-4 py-3 text-[13px] text-muted">
              Barcode <b className="font-mono">{scannedUpc}</b> saved — discs and game boxes have no
              public barcode catalog, so find the title above and the code is stored with the item.
            </p>
          )}
        </>
      )}
    </section>
  );
}

function SearchMode({
  type,
  label,
  available,
  query,
  onQuery,
  platform,
  onPlatform,
  onPick,
}: {
  type: ItemType;
  /** Name of the catalog being searched, as the user should see it. */
  label: string;
  available: boolean;
  query: string;
  onQuery: (q: string) => void;
  platform: string;
  onPlatform: (p: string) => void;
  onPick: (r: EnrichResult) => void;
}) {
  // Seeded from the lifted query so returning from the confirm form shows
  // the cached results straight away instead of an empty list.
  const [debounced, setDebounced] = useState(query);
  // useEffect, not useMemo: only effects run their cleanup, and the cleanup
  // is what cancels the previous keystroke's timer (the actual debounce).
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);
  const isGame = type === "game";
  const narrowed = isGame && Boolean(platform);
  const catalog = usePlatformCatalog(isGame);
  const platformOptions = useMemo(
    () => [...new Set([...COMMON_PLATFORMS, ...(catalog.data?.platforms.map((p) => p.name) ?? [])])],
    [catalog.data],
  );
  const search = useEnrichSearch(type, debounced, narrowed ? platform : "");
  const details = useEnrichDetails();
  // A cleared box keeps no results: the query is disabled then, and the
  // held-over placeholder data would otherwise linger on screen.
  const ready = debounced.trim().length >= 2;
  const results = ready ? (search.data?.results ?? []) : [];
  // True while the newly typed term loads and `results` still belongs to
  // the previous one — dim the list, don't tear it down.
  const stale = search.isPlaceholderData || search.isFetching;

  function pick(result: EnrichResult) {
    // Movies and TV get a richer record (director/creator, runtime) on
    // selection; music gets its tracklist, which the search omits.
    if ((type === "movie" || type === "tv" || type === "music") && result.external_id) {
      details.mutate(
        { type, externalId: result.external_id },
        {
          onSuccess: (data) => onPick(data.results[0] ?? result),
          onError: () => onPick(result),
        },
      );
    } else {
      onPick(result);
    }
  }

  if (!available) {
    return (
      <div className="rounded-xl bg-surface px-5 py-4 text-sm text-muted">
        {label} isn't configured (missing API key), so search is off — use{" "}
        <b>Manual entry</b> instead. The README explains where to get a free key.
      </div>
    );
  }

  return (
    <div>
      <div className="flex gap-2 max-[520px]:flex-col">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 opacity-45" />
          <input
            type="search"
            autoFocus
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder={`Search ${label} by ${type === "music" ? "artist or album" : "title"}${
              type === "book" ? " or ISBN" : ""
            }…`}
            className="input w-full"
            style={{ paddingLeft: 38 }}
          />
        </div>
        {/* Games only: narrow the catalog to one platform — it also becomes
            the platform the copy is filed under on the next step. */}
        {isGame && (
          <select
            aria-label="Filter by platform"
            value={platform}
            onChange={(e) => onPlatform(e.target.value)}
            className="input cursor-pointer appearance-none text-[13px] font-semibold text-body max-[520px]:w-full"
          >
            <option value="">All platforms</option>
            {platformOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        )}
      </div>
      <div
        className={`mt-3.5 flex flex-col gap-2 transition-opacity ${
          stale && results.length > 0 ? "opacity-55" : ""
        }`}
      >
        {ready && stale && results.length === 0 && <div className="skeleton h-[74px] rounded-xl" />}
        {results.map((result, index) => (
          <ResultRow key={index} result={result} onPick={() => pick(result)} busy={details.isPending} />
        ))}
        {ready && !stale && results.length === 0 && (
          <p className="px-1 py-2 text-sm text-muted">
            {narrowed
              ? `Nothing found for “${debounced}” on ${platform} — try another spelling, widen to All platforms, or add it manually.`
              : `Nothing found for “${debounced}” — try another spelling or add it manually.`}
          </p>
        )}
      </div>
    </div>
  );
}

function ResultRow({
  result,
  onPick,
  busy,
}: {
  result: EnrichResult;
  onPick: () => void;
  busy: boolean;
}) {
  const meta = result.metadata;
  const sub = [
    Array.isArray(meta.authors) ? meta.authors.slice(0, 2).join(", ") : null,
    typeof meta.artist === "string" ? meta.artist : null,
    typeof meta.developer === "string" ? meta.developer : null,
    meta.year ? String(meta.year) : null,
    meta.page_count ? `${meta.page_count} pp` : null,
    typeof meta.platform === "string" ? meta.platform : null,
    // Records: the pressing, which is what tells two near-identical
    // catalog entries apart.
    typeof meta.media === "string" ? meta.media : null,
    typeof meta.label === "string" ? meta.label : null,
    typeof meta.catalog_number === "string" ? meta.catalog_number : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      type="button"
      onClick={onPick}
      disabled={busy}
      className="flex items-center gap-3.5 rounded-xl bg-surface px-3.5 py-3 text-left transition-colors hover:bg-raised disabled:opacity-60"
    >
      <span
        className="h-14 w-[38px] flex-none overflow-hidden rounded-md border border-line-strong"
        style={{
          background:
            "repeating-linear-gradient(135deg, var(--poster-stripe) 0 5px, transparent 5px 10px), var(--poster-bg)",
        }}
      >
        {result.cover_url && (
          <img src={result.cover_url} alt="" loading="lazy" className="h-full w-full object-cover" />
        )}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-bold">{result.title}</span>
        <span className="block truncate text-[12.5px] text-muted">{sub}</span>
      </span>
      <span className="ml-auto flex-none font-mono text-[10.5px] tracking-[0.08em] text-accent">
        SELECT →
      </span>
    </button>
  );
}

function ScanMode({
  onMatch,
  onUpc,
}: {
  /** A code the catalogs recognised — the result carries its own type. */
  onMatch: (r: EnrichResult) => void;
  onUpc: (code: string) => void;
}) {
  const navigate = useNavigate();
  const lookup = useBarcodeLookup();
  const [manualCode, setManualCode] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  function handleCode(code: string) {
    setStatus(`Looking up ${code}…`);
    lookup.mutate(code, {
      onSuccess: (data) => {
        if (data.owned_item_id) {
          // Already on the shelf: open it rather than adding a second copy.
          // The code travels along so the item page can say why you're there.
          navigate(`/items/${data.owned_item_id}`, { state: { scanned: data.code } });
        } else if (data.matched && data.result) {
          onMatch(data.result);
        } else if (data.kind === "isbn") {
          setStatus(`No book found for ISBN ${data.code} — try search or manual entry.`);
        } else {
          onUpc(data.code);
        }
      },
      onError: (err) => setStatus((err as Error).message),
    });
  }

  return (
    <div>
      <BarcodeScanner onDetected={handleCode} />
      <p className="mt-3.5 flex items-baseline gap-2 text-[13px] text-muted">
        <b className="font-mono text-xs">ISBN</b>
        Books fill in automatically from Open Library.
      </p>
      <p className="mt-1.5 flex items-baseline gap-2 text-[13px] text-muted">
        <b className="font-mono text-xs">UPC</b>
        Sleeve barcodes fill in from the music catalogs.
      </p>
      <form
        className="mt-2 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (manualCode.trim()) handleCode(manualCode.trim());
        }}
      >
        <input
          value={manualCode}
          onChange={(e) => setManualCode(e.target.value)}
          placeholder="…or type the barcode digits"
          inputMode="numeric"
          className="input min-w-0 flex-1"
        />
        <button type="submit" className="btn btn-ghost btn-sm" disabled={lookup.isPending}>
          Look up
        </button>
      </form>
      {status && <p className="mt-2.5 text-[13px] text-muted">{status}</p>}
    </div>
  );
}

/** Photograph the cover and let a vision model read the text off it — the way
 * in for discs and game boxes, which no barcode catalog covers. One read gives
 * the title, the console and the publisher, and the catalog decides which of
 * them was real; whatever comes back is a search term, never an item. */
function PhotoMode({
  type,
  onRead,
}: {
  type: ItemType;
  onRead: (read: PhotoRead) => void;
}) {
  const read = usePhotoRead(type);

  return (
    <div>
      <label
        className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-line-strong px-5 py-8 text-center hover:bg-surface"
        style={{ borderWidth: 1 }}
      >
        <span className="text-[15px] font-semibold text-text">
          {read.isPending ? "Reading the cover…" : "Take a photo of the front"}
        </span>
        <span className="text-[13px] text-muted">
          Hold the box upright and fill the frame — the title, console and
          publisher are read off it in one go.
        </span>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          aria-label="Photo of the cover"
          className="hidden"
          disabled={read.isPending}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) read.mutate(file, { onSuccess: onRead });
          }}
        />
      </label>
      <p className="mt-3.5 text-[13px] text-muted">
        The title becomes a catalog search, so a partial read is fine — you pick the match.
      </p>
      {read.isError && (
        <p className="mt-2.5 text-[13px] text-danger">{(read.error as Error).message}</p>
      )}
    </div>
  );
}

/** Final form: prefilled from a catalog pick, or blank for manual entry. */
function ConfirmForm({
  type,
  label,
  draft,
  scannedUpc,
  preferredPlatform = "",
  onBack,
}: {
  type: ItemType;
  /** Name of the catalog the draft came from. */
  label: string;
  draft: EnrichResult | null;
  scannedUpc: string | null;
  /** The platform picked in the search filter — preselected here. */
  preferredPlatform?: string;
  onBack?: () => void;
}) {
  const navigate = useNavigate();
  const create = useCreateItem();
  const meta = draft?.metadata ?? {};

  const [title, setTitle] = useState(draft?.title ?? "");
  const [creator, setCreator] = useState(
    Array.isArray(meta.authors)
      ? meta.authors.join(", ")
      : typeof meta.artist === "string"
        ? meta.artist
        : typeof meta.director === "string"
          ? meta.director
          : typeof meta.developer === "string"
            ? meta.developer
            : "",
  );
  const [year, setYear] = useState(meta.year ? String(meta.year) : "");
  const [count, setCount] = useState(
    meta.page_count
      ? String(meta.page_count)
      : meta.runtime
        ? String(meta.runtime)
        : meta.number_of_seasons
          ? String(meta.number_of_seasons)
          : meta.track_count
            ? String(meta.track_count)
            : "",
  );
  const [format, setFormat] = useState("physical");
  // Records come out of the catalog with their carrier already known.
  const [media, setMedia] = useState(typeof meta.media === "string" ? meta.media : "");
  const [storefront, setStorefront] = useState("");
  const [status, setStatus] = useState<ItemStatus>("backlog");
  const [price, setPrice] = useState("");
  const [date, setDate] = useState("");

  const countLabel =
    type === "book"
      ? "Pages"
      : type === "movie"
        ? "Runtime (min)"
        : type === "tv"
          ? "Seasons"
          : type === "music"
            ? "Tracks"
            : "Platform";
  const creatorLabel =
    type === "book"
      ? "Author(s)"
      : type === "movie"
        ? "Director"
        : type === "tv"
          ? "Creator"
          : type === "music"
            ? "Artist"
            : "Developer";

  // The catalog reports every platform a game was released on; the user
  // stores the ONE they own (so the library can filter per platform).
  // When the game was found in the catalog, offer only its release
  // platforms ("Other…" stays as the escape hatch); the full list is for
  // manual entries.
  const detectedPlatforms =
    typeof meta.platform === "string" ? meta.platform.split(",").map((p) => p.trim()) : [];
  const catalog = usePlatformCatalog(type === "game" && detectedPlatforms.length === 0);
  const platformOptions = detectedPlatforms.length
    ? [...new Set([preferredPlatform, ...detectedPlatforms].filter(Boolean))]
    : [
        ...new Set([...COMMON_PLATFORMS, ...(catalog.data?.platforms.map((p) => p.name) ?? [])]),
      ];
  const [platform, setPlatform] = useState(
    preferredPlatform || (detectedPlatforms.length === 1 ? detectedPlatforms[0] : ""),
  );
  const [customPlatform, setCustomPlatform] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const metadata: Record<string, unknown> = { ...meta };
    if (type === "book") {
      metadata.authors = creator ? creator.split(",").map((s) => s.trim()) : [];
      if (count) metadata.page_count = Number(count);
    } else if (type === "movie") {
      if (creator) metadata.director = creator;
      if (count) metadata.runtime = Number(count);
      if (media && format === "physical" && status !== "wishlist") metadata.media = media;
    } else if (type === "tv") {
      if (creator) metadata.director = creator;
      if (count) metadata.number_of_seasons = Number(count);
      if (media && format === "physical" && status !== "wishlist") metadata.media = media;
    } else if (type === "music") {
      if (creator) metadata.artist = creator;
      if (count) metadata.track_count = Number(count);
      // The carrier belongs to the pressing, so a wishlisted record keeps
      // the one the catalog reported — it's the copy being hunted for.
      // A digital copy has no carrier at all.
      if (media && (status === "wishlist" || format === "physical")) metadata.media = media;
      else delete metadata.media;
    } else {
      if (creator) metadata.developer = creator;
      if (platform) metadata.platform = platform;
      if (detectedPlatforms.length > 1) metadata.released_on = detectedPlatforms;
      if (storefront && format === "digital" && status !== "wishlist") {
        metadata.storefront = storefront;
      }
    }
    if (year) metadata.year = Number(year);
    if (scannedUpc) metadata.upc = scannedUpc;

    const isWishlist = status === "wishlist";
    create.mutate(
      {
        type,
        title,
        status,
        format: isWishlist ? null : format,
        metadata,
        cover_url: draft?.cover_url ?? null,
        purchase_price: !isWishlist && price ? Number(price) : null,
        currency: !isWishlist && price ? "EUR" : null,
        acquisition_date: !isWishlist && date ? date : null,
        progress_total: type === "book" && count ? Number(count) : null,
      },
      { onSuccess: (item) => navigate(`/items/${item.id}`) },
    );
  }

  return (
    <form onSubmit={submit} className="grid grid-cols-2 gap-3.5">
      {draft && (
        <div className="col-span-2 flex items-center gap-3.5 rounded-lg bg-surface px-4 py-2.5">
          {draft.cover_url && (
            <img
              src={draft.cover_url}
              alt={`Cover of ${draft.title}`}
              className="h-16 w-11 flex-none rounded-md border border-line-strong object-cover"
              style={{ background: "var(--raised)" }}
            />
          )}
          <p className="m-0 flex-1 text-[13px] text-muted">
            Prefilled from {label} — check and adjust.
          </p>
          {onBack && (
            <button type="button" onClick={onBack} className="flex-none text-[13px] font-semibold text-accent">
              ← results
            </button>
          )}
        </div>
      )}
      <label className="field col-span-2">
        Title
        <input required value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="field">
        {creatorLabel}
        <input value={creator} onChange={(e) => setCreator(e.target.value)} />
      </label>
      <label className="field">
        Year
        <input inputMode="numeric" value={year} onChange={(e) => setYear(e.target.value)} />
      </label>
      {type === "game" ? (
        <label className="field">
          Platform
          {customPlatform ? (
            <input
              autoFocus
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              placeholder="Type your platform…"
            />
          ) : (
            <select
              value={platform}
              onChange={(e) => {
                if (e.target.value === "__other__") {
                  setCustomPlatform(true);
                  setPlatform("");
                } else {
                  setPlatform(e.target.value);
                }
              }}
            >
              <option value="">Choose platform…</option>
              {platformOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
              <option value="__other__">Other…</option>
            </select>
          )}
        </label>
      ) : (
        <label className="field">
          {countLabel}
          <input inputMode="numeric" value={count} onChange={(e) => setCount(e.target.value)} />
        </label>
      )}
      <label className="field">
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value as ItemStatus)}>
          <option value="backlog">Backlog</option>
          <option value="wishlist">Wishlist</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
        </select>
      </label>
      {status !== "wishlist" && (
        <>
          <label className="field">
            Format
            <select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="physical">Physical</option>
              <option value="digital">Digital</option>
            </select>
          </label>
          {/* Disc format for films, carrier for records. */}
          {mediaOptions(type).length > 0 && format === "physical" && (
            <label className="field">
              Media
              <select value={media} onChange={(e) => setMedia(e.target.value)}>
                <option value="">Choose…</option>
                {mediaOptions(type).map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
          )}
          {type === "game" && format === "digital" && (
            <label className="field">
              Storefront
              <select value={storefront} onChange={(e) => setStorefront(e.target.value)}>
                <option value="">Choose…</option>
                {STOREFRONTS.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
          )}
          <label className="field">
            Price paid (EUR)
            <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="optional" />
          </label>
          <label className="field">
            Acquired on
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
        </>
      )}
      {create.isError && (
        <p className="col-span-2 m-0 text-[13px] text-movie">{(create.error as Error).message}</p>
      )}
      <div className="col-span-2 mt-1.5 flex justify-end gap-2.5">
        <button type="submit" className="btn" disabled={create.isPending || !title.trim()}>
          {create.isPending ? "Adding…" : status === "wishlist" ? "Add to wishlist" : "Add to shelf"}
        </button>
      </div>
    </form>
  );
}
