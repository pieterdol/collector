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
  usePlatformCatalog,
  useProviders,
} from "../lib/queries";
import type { EnrichResult, ItemStatus, ItemType } from "../lib/types";

const PROVIDER_LABEL: Record<ItemType, string> = {
  book: "Open Library",
  movie: "TMDB",
  game: "IGDB",
};

type Mode = "search" | "scan" | "manual";

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
  const providers = useProviders();

  const available = useMemo(() => {
    const map: Partial<Record<ItemType, boolean>> = {};
    for (const p of providers.data?.providers ?? []) map[p.type] = p.available;
    return map;
  }, [providers.data]);

  // w-full matters: without it, a flex-column item with mx-auto shrink-wraps
  // to its content's intrinsic width, and long unbreakable result lines
  // (game platform lists) push the page past the viewport on mobile.
  return (
    <section className="mx-auto w-full max-w-[640px]">
      <h2 className="m-0 mb-1 text-[26px] font-extrabold tracking-tight">Add to collection</h2>
      <p className="m-0 mb-6 text-[14.5px] text-muted">
        Search a catalog, scan a barcode, or enter it yourself.
      </p>

      <div className="mb-5 grid grid-cols-3 gap-2.5">
        {(Object.keys(PROVIDER_LABEL) as ItemType[]).map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={type === t}
            onClick={() => {
              setType(t);
              setDraft(null);
              if (t !== "book" && mode === "scan") setMode("search");
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
              {PROVIDER_LABEL[t]}
            </small>
          </button>
        ))}
      </div>

      {draft ? (
        <ConfirmForm
          type={type}
          draft={draft}
          scannedUpc={scannedUpc}
          onBack={() => setDraft(null)}
        />
      ) : (
        <>
          <div className="mb-5 flex w-fit gap-1.5 rounded-[10px] border border-line bg-surface p-1" role="tablist">
            {(type === "book" ? (["search", "scan", "manual"] as Mode[]) : (["search", "manual"] as Mode[])).map((m) => (
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
                {m === "search" ? "Search" : m === "scan" ? "Scan barcode" : "Manual entry"}
              </button>
            ))}
          </div>

          {mode === "search" && (
            <SearchMode
              type={type}
              available={available[type] ?? false}
              onPick={(result) => {
                setScannedUpc(null);
                setDraft(result);
              }}
            />
          )}
          {mode === "scan" && (
            <ScanMode
              onBook={(result) => {
                setScannedUpc(null);
                setDraft(result);
              }}
              onUpc={(code) => {
                setScannedUpc(code);
                setMode("search");
              }}
            />
          )}
          {mode === "manual" && <ConfirmForm type={type} draft={null} scannedUpc={scannedUpc} />}

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
  available,
  onPick,
}: {
  type: ItemType;
  available: boolean;
  onPick: (r: EnrichResult) => void;
}) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  // useEffect, not useMemo: only effects run their cleanup, and the cleanup
  // is what cancels the previous keystroke's timer (the actual debounce).
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);
  const search = useEnrichSearch(type, debounced);
  const details = useEnrichDetails();

  function pick(result: EnrichResult) {
    // Movies get a richer record (director, runtime) on selection.
    if (type === "movie" && result.external_id) {
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
        {PROVIDER_LABEL[type]} isn't configured (missing API key), so search is off — use{" "}
        <b>Manual entry</b> instead. The README explains where to get a free key.
      </div>
    );
  }

  return (
    <div>
      <div className="relative">
        <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 opacity-45" />
        <input
          type="search"
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Search ${PROVIDER_LABEL[type]} by title${type === "book" ? " or ISBN" : ""}…`}
          className="input w-full"
          style={{ paddingLeft: 38 }}
        />
      </div>
      <div className="mt-3.5 flex flex-col gap-2">
        {search.isLoading && debounced.length >= 2 && (
          <div className="skeleton h-[74px] rounded-xl" />
        )}
        {(search.data?.results ?? []).map((result, index) => (
          <ResultRow key={index} result={result} onPick={() => pick(result)} busy={details.isPending} />
        ))}
        {search.data && search.data.results.length === 0 && debounced.length >= 2 && (
          <p className="px-1 py-2 text-sm text-muted">
            Nothing found for “{debounced}” — try another spelling or add it manually.
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
    typeof meta.developer === "string" ? meta.developer : null,
    meta.year ? String(meta.year) : null,
    meta.page_count ? `${meta.page_count} pp` : null,
    typeof meta.platform === "string" ? meta.platform : null,
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
            "repeating-linear-gradient(135deg, rgba(255,255,255,0.05) 0 5px, transparent 5px 10px), var(--raised)",
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
  onBook,
  onUpc,
}: {
  onBook: (r: EnrichResult) => void;
  onUpc: (code: string) => void;
}) {
  const lookup = useBarcodeLookup();
  const [manualCode, setManualCode] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  function handleCode(code: string) {
    setStatus(`Looking up ${code}…`);
    lookup.mutate(code, {
      onSuccess: (data) => {
        if (data.matched && data.result) {
          onBook(data.result);
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

/** Final form: prefilled from a catalog pick, or blank for manual entry. */
function ConfirmForm({
  type,
  draft,
  scannedUpc,
  onBack,
}: {
  type: ItemType;
  draft: EnrichResult | null;
  scannedUpc: string | null;
  onBack?: () => void;
}) {
  const navigate = useNavigate();
  const create = useCreateItem();
  const meta = draft?.metadata ?? {};

  const [title, setTitle] = useState(draft?.title ?? "");
  const [creator, setCreator] = useState(
    Array.isArray(meta.authors)
      ? meta.authors.join(", ")
      : typeof meta.director === "string"
        ? meta.director
        : typeof meta.developer === "string"
          ? meta.developer
          : "",
  );
  const [year, setYear] = useState(meta.year ? String(meta.year) : "");
  const [count, setCount] = useState(
    meta.page_count ? String(meta.page_count) : meta.runtime ? String(meta.runtime) : "",
  );
  const [format, setFormat] = useState("physical");
  const [media, setMedia] = useState("");
  const [storefront, setStorefront] = useState("");
  const [status, setStatus] = useState<ItemStatus>("backlog");
  const [price, setPrice] = useState("");
  const [date, setDate] = useState("");

  const countLabel = type === "book" ? "Pages" : type === "movie" ? "Runtime (min)" : "Platform";
  const creatorLabel = type === "book" ? "Author(s)" : type === "movie" ? "Director" : "Developer";

  // The catalog reports every platform a game was released on; the user
  // stores the ONE they own (so the library can filter per platform).
  const detectedPlatforms =
    typeof meta.platform === "string" ? meta.platform.split(",").map((p) => p.trim()) : [];
  const catalog = usePlatformCatalog(type === "game");
  const platformOptions = [
    ...new Set([
      ...detectedPlatforms,
      ...COMMON_PLATFORMS,
      ...(catalog.data?.platforms.map((p) => p.name) ?? []),
    ]),
  ];
  const [platform, setPlatform] = useState(
    detectedPlatforms.length === 1 ? detectedPlatforms[0] : "",
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
        <p className="col-span-2 m-0 flex items-center justify-between rounded-lg bg-surface px-4 py-2.5 text-[13px] text-muted">
          Prefilled from {PROVIDER_LABEL[type]} — check and adjust.
          {onBack && (
            <button type="button" onClick={onBack} className="font-semibold text-accent">
              ← results
            </button>
          )}
        </p>
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
          {type === "movie" && format === "physical" && (
            <label className="field">
              Media
              <select value={media} onChange={(e) => setMedia(e.target.value)}>
                <option value="">Choose…</option>
                <option>DVD</option>
                <option>Blu-ray</option>
                <option>Ultra HD Blu-ray</option>
                <option>VHS</option>
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
