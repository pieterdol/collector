/** Library: loan banner, type chips, status/sort dropdowns, poster grid ⇄ table. */

import { Link, useSearchParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { ItemTable } from "../components/ItemTable";
import { PosterCard } from "../components/PosterCard";
import { PosterGridSkeleton } from "../components/Skeletons";
import { useItems, usePlatforms, useStats, useUpdateItem } from "../lib/queries";

const TYPE_CHIPS = [
  { value: "", label: "All" },
  { value: "book", label: "Books" },
  { value: "movie", label: "Movies" },
  { value: "game", label: "Games" },
];

export default function Shelf() {
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? "";
  const status = params.get("status") ?? "";
  const platform = params.get("platform") ?? "";
  const q = params.get("q") ?? "";
  const sort = params.get("sort") ?? "added";
  const view = params.get("view") ?? "grid";

  const { data, isLoading } = useItems({
    type: type ? [type] : undefined,
    // The library shows what you own; the wishlist is its own page.
    status: status ? [status] : ["backlog", "in_progress", "completed", "abandoned"],
    platform: platform || undefined,
    q: q || undefined,
    sort,
  });
  const platforms = usePlatforms();

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key === "type" && value !== "game") next.delete("platform");
    setParams(next, { replace: true });
  }

  const items = data?.items ?? [];
  const filtersActive = Boolean(type || status || q);

  return (
    <>
      <LoanBanner />
      <section className="flex flex-wrap items-center gap-2">
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
        <div className="ml-auto flex items-center gap-2 text-[12.5px] text-faint">
          <span>{data ? `${data.total} item${data.total === 1 ? "" : "s"}` : ""}</span>
          {type === "game" && (platforms.data?.platforms.length ?? 0) > 0 && (
            <select
              aria-label="Platform"
              value={platform}
              onChange={(e) => setParam("platform", e.target.value)}
              className="input cursor-pointer appearance-none py-[7px] text-[12.5px] font-semibold text-body"
            >
              <option value="">All platforms</option>
              {platforms.data!.platforms.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          )}
          <select
            aria-label="Status"
            value={status}
            onChange={(e) => setParam("status", e.target.value)}
            className="input cursor-pointer appearance-none py-[7px] text-[12.5px] font-semibold text-body"
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
            className="input cursor-pointer appearance-none py-[7px] text-[12.5px] font-semibold text-body"
          >
            <option value="added">Recently added</option>
            <option value="title">Title A–Z</option>
            <option value="rating">Rating</option>
            <option value="updated">Recently updated</option>
          </select>
        </div>
      </section>

      {isLoading ? (
        <PosterGridSkeleton />
      ) : items.length === 0 ? (
        <EmptyState
          title={filtersActive ? "Nothing here" : "Your library is empty"}
          message={
            filtersActive
              ? "No items match these filters. Clear them, or add something new."
              : "Add your first book, movie or game to get started."
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
    </>
  );
}

/** Accent-tinted banner for items currently out on loan. */
function LoanBanner() {
  const { data } = useStats();
  const loans = data?.loans ?? [];
  if (loans.length === 0) return null;
  const first = loans[0];
  return (
    <section
      className="flex flex-wrap items-center gap-3 rounded-xl px-4 py-3 text-[13.5px]"
      style={{
        background: "color-mix(in oklch, var(--accent) 8%, transparent)",
        border: "1px solid color-mix(in oklch, var(--accent) 25%, transparent)",
      }}
    >
      <span className="h-2 w-2 flex-none rounded-full" style={{ background: "var(--accent)" }} />
      <span className="min-w-0">
        <strong>{first.title}</strong> is with {first.borrowed_by}
        {first.loaned_date &&
          ` since ${new Date(first.loaned_date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}`}
        {loans.length > 1 && ` · +${loans.length - 1} more on loan`}
      </span>
      <MarkReturned id={first.id} />
    </section>
  );
}

function MarkReturned({ id }: { id: string }) {
  const update = useUpdateItem(id);
  return (
    <button
      type="button"
      className="ml-auto text-[12.5px] font-semibold text-accent"
      disabled={update.isPending}
      onClick={() => update.mutate({ returned_date: new Date().toISOString().slice(0, 10) })}
    >
      Mark returned
    </button>
  );
}
