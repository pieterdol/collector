/** Upcoming: future releases across the library and wishlist, as a
 * timeline grouped by month (or bare year for year-only dates). */

import { Link, useSearchParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { HeartIcon } from "../components/icons";
import { coverSrc, describeItem } from "../components/PosterCard";
import { useItems } from "../lib/queries";
import { TYPE_LABEL, type Item } from "../lib/types";
import { groupByRelease, type ReleaseInfo } from "../lib/upcoming";

const TYPE_CHIPS = [
  { value: "", label: "All" },
  { value: "book", label: "Books" },
  { value: "movie", label: "Movies" },
  { value: "tv", label: "TV" },
  { value: "game", label: "Games" },
  { value: "music", label: "Music" },
];

export default function Upcoming() {
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? "";
  const { data, isLoading } = useItems({
    upcoming: "true",
    sort: "release",
    type: type ? [type] : undefined,
  });

  function setType(value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set("type", value);
    else next.delete("type");
    setParams(next, { replace: true });
  }

  const items = data?.items ?? [];
  const groups = groupByRelease(items);

  return (
    <>
      <section className="flex flex-wrap items-center gap-2">
        {TYPE_CHIPS.map((chip) => (
          <button
            key={chip.value}
            type="button"
            className="chip"
            aria-pressed={type === chip.value}
            onClick={() => setType(chip.value)}
          >
            {chip.label}
          </button>
        ))}
        {!isLoading && (
          <span className="ml-auto text-[12.5px] text-faint">{items.length} upcoming</span>
        )}
      </section>

      {isLoading ? (
        <TimelineSkeleton />
      ) : groups.length === 0 ? (
        <EmptyState
          title="Nothing on the horizon"
          message="No upcoming releases in your library or wishlist. Add wishlist items with a release date and they'll show up here."
          action={
            <Link to="/add" className="btn no-underline">
              + Add to wishlist
            </Link>
          }
        />
      ) : (
        groups.map((group) => (
          <div key={group.label} className="flex flex-col gap-2.5">
            <div className="flex items-center gap-3">
              <span className="whitespace-nowrap text-xs font-semibold uppercase tracking-[0.08em] text-muted">
                {group.label}
              </span>
              <span className="h-px flex-1 bg-line" />
            </div>
            <div className="panel overflow-hidden">
              {group.rows.map(({ item, info }) => (
                <UpcomingRow key={item.id} item={item} info={info} />
              ))}
            </div>
          </div>
        ))
      )}
    </>
  );
}

function UpcomingRow({ item, info }: { item: Item; info: ReleaseInfo }) {
  const meta = describeItem(item);
  return (
    <Link
      to={`/items/${item.id}`}
      state={{ from: "upcoming" }}
      className="flex items-center gap-3.5 border-b border-line px-4 py-3 no-underline transition-colors last:border-b-0 hover:bg-raised"
    >
      <div
        className="grid h-12 w-[34px] flex-none place-items-center overflow-hidden rounded-md border border-line-strong"
        style={{ background: "var(--poster-bg)" }}
      >
        {item.cover_path && (
          <img src={coverSrc(item)!} alt="" loading="lazy" className="h-full w-full object-cover" />
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex flex-wrap items-center gap-2">
          {/* Mobile: full-width title so the badges share one line below it. */}
          <span className="text-[13.5px] font-semibold leading-[1.3] text-text max-[820px]:w-full">
            {item.title}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10.5px] font-semibold"
            style={{
              color: `var(--${item.type})`,
              background: `color-mix(in oklch, var(--${item.type}) 15%, transparent)`,
            }}
          >
            {TYPE_LABEL[item.type]}
          </span>
          {item.status === "wishlist" && (
            <span className="inline-flex items-center gap-1 rounded-full border border-line-strong px-2 py-0.5 text-[10.5px] font-semibold text-muted">
              <HeartIcon size={9} /> wishlist
            </span>
          )}
        </div>
        {meta && <span className="truncate text-xs text-faint">{meta}</span>}
      </div>

      {/* Mobile: date above countdown in a right-aligned column, so the
          title and badges keep the row's width. */}
      <div className="flex flex-none items-center gap-2.5 max-[820px]:flex-col max-[820px]:items-end max-[820px]:justify-center max-[820px]:gap-1.5">
        <span className="font-mono text-[12.5px] text-body">{info.dateLabel}</span>
        {info.chip && (
          <span
            className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
              info.soon
                ? "font-bold text-accent-ink"
                : "border border-line-strong bg-raised text-muted"
            }`}
            style={info.soon ? { background: "var(--accent)" } : undefined}
          >
            {info.chip}
          </span>
        )}
      </div>
    </Link>
  );
}

function TimelineSkeleton() {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="skeleton h-4 w-32" />
      <div className="flex flex-col gap-px overflow-hidden rounded-[14px] border border-line">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="skeleton h-[72px] rounded-none" />
        ))}
      </div>
    </div>
  );
}
