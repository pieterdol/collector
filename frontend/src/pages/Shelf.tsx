/** Main collection view: poster grid ⇄ dense table, filter pills, sort. */

import { useSearchParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { GridIcon, RowsIcon } from "../components/icons";
import { ItemTable } from "../components/ItemTable";
import { PosterCard } from "../components/PosterCard";
import { PosterGridSkeleton } from "../components/Skeletons";
import { useItems } from "../lib/queries";

const TYPES = [
  { value: "book", label: "Books" },
  { value: "movie", label: "Movies" },
  { value: "game", label: "Games" },
];
const STATUSES = [
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "backlog", label: "Backlog" },
];

export default function Shelf() {
  const [params, setParams] = useSearchParams();
  const types = params.getAll("type");
  const statuses = params.getAll("status");
  const q = params.get("q") ?? "";
  const sort = params.get("sort") ?? "added";
  const view = params.get("view") ?? "grid";

  // The shelf shows what you own; the wishlist has its own page.
  const effectiveStatuses = statuses.length
    ? statuses
    : ["backlog", "in_progress", "completed", "abandoned"];

  const { data, isLoading } = useItems({
    type: types.length ? types : undefined,
    status: effectiveStatuses,
    q: q || undefined,
    sort,
  });

  function toggleMulti(key: "type" | "status", value: string) {
    const next = new URLSearchParams(params);
    const current = next.getAll(key);
    next.delete(key);
    for (const v of current.includes(value) ? current.filter((v) => v !== value) : [...current, value]) {
      next.append(key, v);
    }
    setParams(next, { replace: true });
  }

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  }

  const items = data?.items ?? [];
  const filtersActive = types.length > 0 || statuses.length > 0 || q !== "";

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <div className="flex gap-2">
          {TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              className="pill"
              aria-pressed={types.includes(t.value)}
              onClick={() => toggleMulti("type", t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {STATUSES.map((s) => (
            <button
              key={s.value}
              type="button"
              className="pill"
              aria-pressed={statuses.includes(s.value)}
              onClick={() => toggleMulti("status", s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-faint">
          {data ? `${data.total} item${data.total === 1 ? "" : "s"}` : ""}
        </span>
        <select
          aria-label="Sort"
          value={sort}
          onChange={(e) => setParam("sort", e.target.value)}
          className="cursor-pointer appearance-none rounded-full border-none bg-surface py-1.5 pl-4 pr-4 text-[13px] font-semibold text-muted outline-none"
        >
          <option value="added">Recently added</option>
          <option value="title">Title A–Z</option>
          <option value="rating">Rating</option>
          <option value="updated">Recently updated</option>
        </select>
        <div className="flex gap-0.5 rounded-full bg-surface p-[3px]" role="group" aria-label="View">
          <button
            type="button"
            title="Gallery view"
            aria-pressed={view === "grid"}
            onClick={() => setParam("view", null)}
            className={`grid place-items-center rounded-full px-3 py-1.5 ${view === "grid" ? "bg-raised text-text" : "text-faint"}`}
          >
            <GridIcon size={14} />
          </button>
          <button
            type="button"
            title="Table view"
            aria-pressed={view === "table"}
            onClick={() => setParam("view", "table")}
            className={`grid place-items-center rounded-full px-3 py-1.5 ${view === "table" ? "bg-raised text-text" : "text-faint"}`}
          >
            <RowsIcon />
          </button>
        </div>
      </div>

      {isLoading ? (
        <PosterGridSkeleton />
      ) : items.length === 0 ? (
        <EmptyState
          title={filtersActive ? "Nothing here" : "Your shelf is empty"}
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
              <Link to="/add" className="btn btn-sm no-underline">
                Add to collection
              </Link>
            )
          }
        />
      ) : view === "table" ? (
        <ItemTable items={items} />
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(154px,1fr))] gap-x-4 gap-y-5 max-[760px]:grid-cols-[repeat(auto-fill,minmax(124px,1fr))] max-[760px]:gap-x-3 max-[760px]:gap-y-4">
          {items.map((item) => (
            <PosterCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}
