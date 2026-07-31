/** Library: type chips, status/sort dropdowns, poster grid ⇄ table. */

import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { GridIcon, RowsIcon } from "../components/icons";
import { ItemTable } from "../components/ItemTable";
import { PosterCard } from "../components/PosterCard";
import { PosterGridSkeleton } from "../components/Skeletons";
import { flattenItemPages, useItemsInfinite, usePlatforms } from "../lib/queries";
import { mediaOptions } from "../lib/types";

const TYPE_CHIPS = [
  { value: "", label: "All" },
  { value: "book", label: "Books" },
  { value: "movie", label: "Movies" },
  { value: "tv", label: "TV" },
  { value: "game", label: "Games" },
  { value: "music", label: "Music" },
];

export default function Shelf() {
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? "";
  const status = params.get("status") ?? "";
  const platform = params.get("platform") ?? "";
  const media = params.get("media") ?? "";
  const q = params.get("q") ?? "";
  const sort = params.get("sort") ?? "added";
  const view = params.get("view") ?? "grid";

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useItemsInfinite({
    type: type ? [type] : undefined,
    // The library shows what you own; the wishlist is its own page.
    status: status ? [status] : ["backlog", "in_progress", "completed", "abandoned"],
    platform: platform || undefined,
    media: media || undefined,
    q: q || undefined,
    sort,
  });
  const platforms = usePlatforms();

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key === "type" && value !== "game") next.delete("platform");
    // Carriers and disc formats don't overlap: a media filter only survives
    // a type change if the new type actually offers it.
    if (key === "type" && !mediaOptions(value).includes(media)) next.delete("media");
    setParams(next, { replace: true });
  }

  const items = flattenItemPages(data?.pages);
  const total = data?.pages[0]?.total;
  const filtersActive = Boolean(type || status || q);

  // On mobile the selects don't fit next to the chips (a select is as wide
  // as its longest option), so they collapse behind a Filters toggle.
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeFilters = [platform, media, status].filter(Boolean).length;

  return (
    <>
      <section className="flex flex-wrap items-center gap-2">
        {/* Desktop: one chip per type; mobile: a single compact select so the
            whole filter bar fits on one row. */}
        <div className="flex flex-wrap items-center gap-2 max-[820px]:hidden">
          {TYPE_CHIPS.map((chip) => (
            <button
              key={chip.value}
              type="button"
              className="chip"
              aria-pressed={type === chip.value}
              onClick={() => setParam("type", chip.value)}
            >
              {chip.label}
            </button>
          ))}
        </div>
        <select
          aria-label="Type"
          value={type}
          onChange={(e) => setParam("type", e.target.value)}
          className="input hidden cursor-pointer appearance-none py-[7px] text-[12.5px] font-semibold text-body max-[820px]:block"
        >
          {TYPE_CHIPS.map((chip) => (
            <option key={chip.value} value={chip.value}>
              {chip.value ? chip.label : "All types"}
            </option>
          ))}
        </select>
        <div className="ml-auto flex items-center gap-2 text-[12.5px] text-faint">
          <span className="whitespace-nowrap">{total !== undefined ? `${total} item${total === 1 ? "" : "s"}` : ""}</span>
          <div className="flex items-center gap-2 max-[820px]:hidden">
            <FilterSelects
              platform={platform}
              media={media}
              status={status}
              sort={sort}
              platformOptions={type === "game" ? (platforms.data?.platforms ?? []) : []}
              mediaChoices={mediaOptions(type)}
              setParam={setParam}
            />
          </div>
          <button
            type="button"
            className="chip hidden max-[820px]:block"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((open) => !open)}
          >
            Filters{activeFilters > 0 && ` · ${activeFilters}`}
          </button>
          <div className="hidden gap-0.5 rounded-[9px] border border-line bg-surface p-0.5 max-[820px]:flex">
            <button
              type="button"
              aria-pressed={view === "grid"}
              aria-label="Gallery view"
              onClick={() => setParam("view", "")}
              className={`grid place-items-center rounded-[7px] px-2 py-1.5 ${view === "grid" ? "bg-raised text-text" : "text-faint"}`}
            >
              <GridIcon size={13} />
            </button>
            <button
              type="button"
              aria-pressed={view === "table"}
              aria-label="Table view"
              onClick={() => setParam("view", "table")}
              className={`grid place-items-center rounded-[7px] px-2 py-1.5 ${view === "table" ? "bg-raised text-text" : "text-faint"}`}
            >
              <RowsIcon size={13} />
            </button>
          </div>
        </div>
      </section>

      {filtersOpen && (
        <section
          role="group"
          aria-label="Filter options"
          className="panel flex flex-col gap-2.5 p-3.5 min-[821px]:hidden"
        >
          <FilterSelects
            platform={platform}
            media={media}
            status={status}
            sort={sort}
            platformOptions={type === "game" ? (platforms.data?.platforms ?? []) : []}
            mediaChoices={mediaOptions(type)}
            setParam={setParam}
            stacked
          />
        </section>
      )}

      {isLoading ? (
        <PosterGridSkeleton />
      ) : items.length === 0 ? (
        <EmptyState
          title={filtersActive ? "Nothing here" : "Your library is empty"}
          message={
            filtersActive
              ? "No items match these filters. Clear them, or add something new."
              : "Add your first book, record, movie or game to get started."
          }
          action={
            filtersActive ? (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setParams({}, { replace: true })}>
                Clear filters
              </button>
            ) : (
              <Link to="/add" className="btn no-underline">
                + Add item
              </Link>
            )
          }
        />
      ) : view === "table" ? (
        <ItemTable items={items} />
      ) : (
        <section className="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-[18px] max-[820px]:grid-cols-[repeat(auto-fill,minmax(128px,1fr))] max-[820px]:gap-3">
          {items.map((item) => (
            <PosterCard key={item.id} item={item} />
          ))}
        </section>
      )}

      <LoadMore
        hasMore={Boolean(hasNextPage)}
        loading={isFetchingNextPage}
        onLoad={fetchNextPage}
      />
    </>
  );
}

/** The platform/status/sort selects; inline on desktop, stacked in the
 * mobile Filters panel. */
function FilterSelects({
  platform,
  media,
  status,
  sort,
  platformOptions,
  mediaChoices,
  setParam,
  stacked = false,
}: {
  platform: string;
  media: string;
  status: string;
  sort: string;
  platformOptions: string[];
  /** Disc formats for films, carriers for records, nothing for the rest. */
  mediaChoices: string[];
  setParam: (key: string, value: string) => void;
  stacked?: boolean;
}) {
  const cls = `input cursor-pointer appearance-none py-[7px] text-[12.5px] font-semibold text-body${
    stacked ? " w-full" : ""
  }`;
  return (
    <>
      {platformOptions.length > 0 && (
        <select
          aria-label="Platform"
          value={platform}
          onChange={(e) => setParam("platform", e.target.value)}
          className={cls}
        >
          <option value="">All platforms</option>
          {platformOptions.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      )}
      {mediaChoices.length > 0 && (
        <select
          aria-label="Media"
          value={media}
          onChange={(e) => setParam("media", e.target.value)}
          className={cls}
        >
          <option value="">All media</option>
          {mediaChoices.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      )}
      <select
        aria-label="Status"
        value={status}
        onChange={(e) => setParam("status", e.target.value)}
        className={cls}
      >
        <option value="">Any status</option>
        <option value="in_progress">In progress</option>
        <option value="completed">Completed</option>
        <option value="backlog">Backlog</option>
        <option value="abandoned">Abandoned</option>
      </select>
      <select
        aria-label="Sort"
        value={sort}
        onChange={(e) => setParam("sort", e.target.value)}
        className={cls}
      >
        <option value="added">Recently added</option>
        <option value="title">Title A–Z</option>
        <option value="rating">Rating</option>
        <option value="updated">Recently updated</option>
      </select>
    </>
  );
}

/** Sentinel that loads the next page when scrolled into view. */
function LoadMore({
  hasMore,
  loading,
  onLoad,
}: {
  hasMore: boolean;
  loading: boolean;
  onLoad: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!hasMore || !ref.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading) onLoad();
      },
      { rootMargin: "600px" }, // start fetching well before the end
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [hasMore, loading, onLoad]);

  if (!hasMore) return null;
  return (
    <div ref={ref} className="flex justify-center py-6">
      <div className="skeleton h-8 w-28 rounded-full" />
    </div>
  );
}
