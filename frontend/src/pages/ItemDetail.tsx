/** Item detail, graphite design: key-art hero with overlapping cover,
 * About + screenshots + review + activity (left), progress + details +
 * loan + danger zone (right). Artwork is fetched once, lazily. */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AcquireDialog } from "../components/AcquireDialog";
import { Lightbox } from "../components/Lightbox";
import { BackIcon } from "../components/icons";
import { coverSrc, describeItem } from "../components/PosterCard";
import { formatDate } from "../lib/dates";
import { RatingStars } from "../components/RatingStars";
import { SeasonsPanel } from "../components/SeasonsPanel";
import { DetailSkeleton } from "../components/Skeletons";
import {
  useActivity,
  useBundleWith,
  useCopies,
  useDeleteActivity,
  useDeleteItem,
  useEnrichSearch,
  useFetchArtwork,
  useFrontCopy,
  useItem,
  useItems,
  useRelinkItem,
  useUnbundleCopy,
  useUpdateItem,
  useUploadCover,
} from "../lib/queries";
import { musicTracks } from "../lib/music";
import type { Item, ItemStatus } from "../lib/types";
import { mediaOptions } from "../lib/types";
import { STATUS_LABEL, copyLabel, progressUnit } from "../lib/types";

const SOURCE_LABEL: Record<string, string> = {
  book: "Open Library",
  movie: "TMDB",
  tv: "TMDB",
  game: "Steam Store / IGDB",
  music: "MusicBrainz / Discogs",
};

/** Which catalog this item's metadata actually came from. Music can come
 * from either of two, and the stored ids say which. */
function sourceLabel(item: Item): string {
  if (item.type === "music") {
    if (item.metadata.discogs_release_id) return "Discogs";
    if (item.metadata.mb_release_id) return "MusicBrainz";
  }
  return SOURCE_LABEL[item.type];
}

export default function ItemDetail() {
  const { id } = useParams();
  const { data: item, isLoading } = useItem(id);

  if (isLoading || !item) {
    return (
      <section>
        <BackLink />
        {isLoading ? <DetailSkeleton /> : <p className="text-muted">Item not found.</p>}
      </section>
    );
  }
  return <Detail item={item} />;
}

/** Items opened from the Upcoming page return there; wishlist items to
 * the wishlist; everything else to the library. */
function BackLink({ wishlist = false }: { wishlist?: boolean }) {
  const location = useLocation();
  const fromUpcoming = (location.state as { from?: string } | null)?.from === "upcoming";
  const [to, label] = fromUpcoming
    ? ["/upcoming", "Upcoming"]
    : wishlist
      ? ["/wishlist", "Wishlist"]
      : ["/", "Library"];
  return (
    <Link
      to={to}
      className="inline-flex w-fit items-center gap-2 rounded-[9px] border border-line bg-surface px-3 py-1.5 text-[12.5px] font-semibold text-muted no-underline hover:bg-raised hover:text-text"
    >
      <BackIcon size={12} /> {label}
    </Link>
  );
}

function Detail({ item }: { item: Item }) {
  const meta = item.metadata;
  const [acquiring, setAcquiring] = useState(false);
  const [shotIndex, setShotIndex] = useState<number | null>(null);

  // Fetch hero/screenshots/description exactly once per item.
  const artwork = useFetchArtwork(item.id);
  const attempted = useRef(false);
  useEffect(() => {
    // Books and records are cover-only: neither catalog carries key art or
    // screenshots, so there is nothing to go and fetch.
    if (attempted.current || meta.artwork_fetched || item.type === "book" || item.type === "music")
      return;
    attempted.current = true;
    artwork.mutate();
  }, [item.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const heroPath = typeof meta.hero_path === "string" ? meta.hero_path : null;
  // Only show the band when real key art exists — no placeholder while
  // fetching, and none for items whose sources have no hero (books,
  // old/delisted games).
  const showHero = Boolean(heroPath);
  const shots = Array.isArray(meta.screenshot_paths) ? (meta.screenshot_paths as string[]) : [];
  const description = typeof meta.description === "string" ? meta.description
    : typeof meta.overview === "string" ? meta.overview : null;

  return (
    <>
      <BackLink wishlist={item.status === "wishlist"} />
      <ScannedNotice item={item} />

      {/* Hero + overlapping cover (books skip the hero band) */}
      <section>
        {showHero && (
        <div className="relative flex h-[240px] items-start justify-end overflow-hidden rounded-2xl border border-line-strong p-4 max-[820px]:h-[150px]">
          <img src={heroPath!} alt="" className="absolute inset-0 h-full w-full object-cover" />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to bottom, transparent 40%, var(--bg))" }} />
        </div>
        )}

        <div
          className={
            showHero
              ? "relative -mt-[72px] flex items-end gap-6 px-7 max-[820px]:-mt-10 max-[820px]:flex-wrap max-[820px]:px-3"
              : "relative flex items-end gap-6 px-1 pt-2 max-[820px]:flex-wrap"
          }
        >
          <div className="flex w-[148px] flex-none flex-col gap-1.5 max-[820px]:w-[104px]">
            <div className="poster shadow-lift">
              {item.cover_path ? (
                <img src={coverSrc(item)!} alt={`Cover of ${item.title}`} />
              ) : (
                <span className="px-2 text-center font-mono text-[10.5px] text-text/45">{item.title}</span>
              )}
            </div>
            <CoverEditor item={item} />
          </div>
          <div className="flex min-w-0 flex-col gap-2 pb-1.5">
            <TitleHeading item={item} />
            <div className="text-[13.5px] text-muted">{describeItem(item)}</div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="pillbadge"
                style={{
                  background: `color-mix(in oklch, var(--${item.type}) 15%, transparent)`,
                  color: `var(--${item.type})`,
                }}
              >
                {item.type}
              </span>
              {item.format && (
                <span className="pillbadge border border-line-strong bg-surface text-muted">{item.format}</span>
              )}
              <StatusPill item={item} />
            </div>
          </div>
          <div className="ml-auto flex gap-2.5 pb-1.5 max-[820px]:ml-0">
            {item.status === "wishlist" && (
              <button type="button" className="btn" onClick={() => setAcquiring(true)}>
                Mark as owned
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Two-column body */}
      <section className="grid grid-cols-[2fr_1fr] items-start gap-3.5 max-[980px]:grid-cols-1">
        <div className="flex min-w-0 flex-col gap-3.5">
          {description && (
            <div className="panel flex flex-col gap-2.5 p-5">
              <div className="paneltitle">About</div>
              <p className="m-0 text-[13.5px] leading-[1.65] text-body">{description}</p>
              <div className="font-mono text-[11.5px] text-dim">
                Metadata via {sourceLabel(item)}
              </div>
            </div>
          )}

          {shots.length > 0 && (
            <div className="panel flex flex-col gap-3 p-5">
              <div className="paneltitle">Screenshots</div>
              <div className="grid grid-cols-2 gap-2.5 max-[560px]:grid-cols-1">
                {shots.map((shot, index) => (
                  <button key={shot} type="button" onClick={() => setShotIndex(index)} className="block">
                    <img
                      src={shot}
                      alt=""
                      loading="lazy"
                      className="aspect-video w-full cursor-zoom-in rounded-[10px] border border-line-strong object-cover"
                      style={{ background: "var(--shot-bg)" }}
                    />
                  </button>
                ))}
              </div>
            </div>
          )}

          {item.type === "tv" && <SeasonsPanel itemId={item.id} />}
          {item.type === "music" && <TracklistPanel item={item} />}
          <ReviewPanel item={item} />
          <ActivityPanel itemId={item.id} unit={progressUnit(item.type)} />
        </div>

        <div className="flex flex-col gap-3.5">
          {progressUnit(item.type) && item.status !== "wishlist" && <ProgressPanel item={item} />}
          <DetailsPanel item={item} />
          <CopiesPanel item={item} />
          <LoanPanel item={item} />
          <DangerZone item={item} />
        </div>
      </section>

      {acquiring && <AcquireDialog item={item} onClose={() => setAcquiring(false)} />}
      {shotIndex !== null && (
        <Lightbox images={shots} index={shotIndex} onClose={() => setShotIndex(null)} onIndex={setShotIndex} />
      )}
    </>
  );
}

/** Why you're here: the scanner sends a code that is already in the
 * collection straight to its item, and this says so. A wishlisted copy is
 * not owned yet — the "Mark as owned" button is right above. */
function ScannedNotice({ item }: { item: Item }) {
  const location = useLocation();
  const code = (location.state as { scanned?: string } | null)?.scanned;
  if (!code) return null;
  return (
    <div
      className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-[14px] px-4 py-3 text-[13px]"
      style={{
        background: "color-mix(in oklch, var(--accent) 7%, transparent)",
        border: "1px solid color-mix(in oklch, var(--accent) 25%, transparent)",
      }}
    >
      <strong className="font-semibold text-text">
        {item.status === "wishlist"
          ? "This is already on your wishlist."
          : "You already own this item."}
      </strong>
      <span className="text-muted">
        Scanned <span className="font-mono">{code}</span>.
      </span>
    </div>
  );
}

/** Tap the heading to rename. The title is the user's, not the catalog's —
 * it already survives a re-link — so a bad import, a barcode that named a
 * book after its edition, or a typo is fixed right here. Escape abandons;
 * an emptied field reverts (every item must keep a title). */
function TitleHeading({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [editing, setEditing] = useState(false);
  const abandoned = useRef(false);
  const heading = "m-0 font-display text-3xl font-bold tracking-[-0.01em] max-[820px]:text-xl";

  const save = (value: string) => {
    setEditing(false);
    const title = value.trim();
    if (abandoned.current) {
      abandoned.current = false;
      return;
    }
    if (!title || title === item.title) return; // blank or unchanged: no PATCH
    update.mutate({ title });
  };

  if (editing) {
    return (
      <input
        autoFocus
        aria-label="Title"
        defaultValue={item.title}
        maxLength={500}
        onBlur={(e) => save(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") abandoned.current = true;
          if (e.key === "Enter" || e.key === "Escape") (e.target as HTMLInputElement).blur();
        }}
        className="input w-full"
        // .input is unlayered CSS, so utility classes lose to it here.
        style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 700 }}
      />
    );
  }
  return (
    <h2 className={heading}>
      {/* No aria-label: the heading's accessible name must stay the title. */}
      <button
        type="button"
        title="Tap to rename"
        onClick={() => setEditing(true)}
        className="text-left hover:text-accent"
      >
        {item.title}
      </button>
    </h2>
  );
}

function StatusPill({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);
  if (item.status === "wishlist") {
    return (
      <span className="pillbadge border border-dashed text-muted" style={{ borderColor: "color-mix(in oklch, var(--accent) 50%, transparent)" }}>
        wishlist
      </span>
    );
  }
  const statuses: ItemStatus[] = ["backlog", "in_progress", "completed", "abandoned"];
  return (
    <span className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="pillbadge cursor-pointer border border-line-strong bg-surface"
        style={{ color: item.status === "completed" ? "var(--done)" : item.status === "in_progress" ? "var(--accent)" : "var(--muted)" }}
      >
        {STATUS_LABEL[item.status]} ▾
      </button>
      {open && (
        <span className="panel absolute left-0 top-8 z-20 flex w-40 flex-col p-1.5 shadow-lift">
          {statuses.map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => {
                setOpen(false);
                if (status !== item.status) update.mutate({ status });
              }}
              className={`rounded-md px-3 py-1.5 text-left text-[12.5px] font-semibold hover:bg-raised ${
                status === item.status ? "text-text" : "text-muted"
              }`}
            >
              {STATUS_LABEL[status]}
            </button>
          ))}
        </span>
      )}
    </span>
  );
}

/** Local-first progress editing: taps update instantly, one PATCH (and
 * one activity record) fires after 5s of quiet — or immediately when the
 * page unmounts. Tap the number to type a value directly. */
function useDebouncedProgress(item: Item, save: (value: number) => void) {
  const server = item.progress_current ? Number(item.progress_current) : 0;
  const [local, setLocal] = useState<number | null>(null);
  const pending = useRef<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const saveRef = useRef(save);
  saveRef.current = save;
  const serverRef = useRef(server);
  serverRef.current = server;

  const flush = () => {
    clearTimeout(timer.current);
    // Landing back on the server value is not a change — no PATCH, no
    // "Progress 0 → 0" activity entry.
    if (pending.current !== null && pending.current !== serverRef.current) {
      saveRef.current(pending.current);
    }
    pending.current = null;
  };
  const set = (value: number) => {
    const clamped = Math.max(0, value);
    setLocal(clamped);
    pending.current = clamped;
    clearTimeout(timer.current);
    timer.current = setTimeout(flush, 5000);
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => flush, []); // unmount → save whatever is pending
  useEffect(() => {
    // server caught up with the local value → drop the local override
    if (local !== null && server === local) setLocal(null);
  }, [server, local]);

  return { shown: local ?? server, set, flush };
}

function ProgressPanel({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const unit = progressUnit(item.type)!;
  const { shown, set, flush } = useDebouncedProgress(item, (value) =>
    update.mutate({ progress_current: value }),
  );
  const total = item.progress_total ? Number(item.progress_total) : null;
  const pct = total ? Math.min(100, Math.round((shown / total) * 100)) : null;
  const step = unit === "pages" ? 10 : 1;
  const [editingTotal, setEditingTotal] = useState(false);
  const [editingValue, setEditingValue] = useState(false);
  const [editingPage, setEditingPage] = useState(false);

  const numberEditor = editingValue ? (
    <input
      autoFocus
      type="number"
      min={0}
      step={unit === "pages" ? 1 : 0.5}
      defaultValue={shown}
      onBlur={(e) => {
        setEditingValue(false);
        if (e.target.value !== "") set(Number(e.target.value));
        flush(); // typing a value is an explicit commit
      }}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      className="input w-24 px-2 py-0.5 font-display text-[22px] font-bold"
    />
  ) : (
    <button
      type="button"
      title="Tap to type a value"
      onClick={() => setEditingValue(true)}
      className="font-display text-[26px] font-bold hover:text-accent"
    >
      {unit === "hours" ? `${shown} h` : (pct !== null ? `${pct}%` : shown)}
    </button>
  );

  const stepper = (
    <div className="flex overflow-hidden rounded-[9px] border border-line-strong">
      <button
        type="button"
        aria-label={`${step} ${unit} less`}
        onClick={() => set(shown - step)}
        className="px-3 py-1 font-mono text-sm text-muted hover:bg-raised hover:text-text"
      >
        −
      </button>
      <button
        type="button"
        aria-label={`${step} ${unit} more`}
        onClick={() => set(total !== null && unit === "pages" ? Math.min(total, shown + step) : shown + step)}
        className="border-l border-line-strong px-3 py-1 font-mono text-sm text-muted hover:bg-raised hover:text-text"
      >
        +
      </button>
    </div>
  );

  if (unit === "hours") {
    return (
      <div className="panel flex flex-col gap-3 p-4.5" style={{ padding: 18 }}>
        <div className="paneltitle">Play time</div>
        <div className="flex items-baseline justify-between">
          {numberEditor}
          {stepper}
        </div>
        <p className="m-0 text-xs text-faint">
          Tap the number to type. Changes save a few seconds after you stop.
        </p>
      </div>
    );
  }

  return (
    <div className="panel flex flex-col gap-3 p-4.5" style={{ padding: 18 }}>
      <div className="paneltitle">Progress</div>
      <div className="flex items-baseline justify-between">
        {numberEditor}
        {/* Both numbers are tap-to-type; an unknown total shows as "?". */}
        <span className="font-mono text-xs text-muted">
          {"p. "}
          {editingPage ? (
            <input
              autoFocus
              type="number"
              min={0}
              aria-label="Current page"
              defaultValue={shown}
              onBlur={(e) => {
                setEditingPage(false);
                if (e.target.value !== "") set(Number(e.target.value));
                flush(); // typing a value is an explicit commit
              }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              className="input w-16 px-1 py-0.5 text-xs"
            />
          ) : (
            <button
              type="button"
              aria-label="Edit current page"
              title="Tap to type the page"
              onClick={() => setEditingPage(true)}
              className="underline decoration-dotted hover:text-text"
            >
              {shown}
            </button>
          )}
          {" / "}
          {editingTotal ? (
            <input
              autoFocus
              type="number"
              min={0}
              aria-label="Total pages"
              defaultValue={total ?? ""}
              onBlur={(e) => {
                setEditingTotal(false);
                const value = e.target.value ? Number(e.target.value) : null;
                if (value !== total) update.mutate({ progress_total: value });
              }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              className="input w-16 px-1 py-0.5 text-xs"
            />
          ) : (
            <button
              type="button"
              aria-label="Edit total pages"
              title="Tap to set the total"
              onClick={() => setEditingTotal(true)}
              className="underline decoration-dotted hover:text-text"
            >
              {total ?? "?"}
            </button>
          )}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-[3px]" style={{ background: "var(--line)" }}>
        <div
          className="h-full rounded-[3px]"
          style={{ width: `${pct ?? 0}%`, background: `var(--${item.type})` }}
        />
      </div>
      <div className="flex items-center gap-2">{stepper}</div>
    </div>
  );
}

/** Read-only tracklist, as the catalog recorded it. Vinyl positions keep
 * their side labels ("A1"), which is how the sleeve reads. */
function TracklistPanel({ item }: { item: Item }) {
  const tracks = musicTracks(item.metadata);
  if (tracks.length === 0) return null;
  return (
    <div className="panel flex flex-col gap-2 p-5">
      <div className="flex items-baseline gap-2">
        <span className="paneltitle">Tracklist</span>
        <span className="text-xs text-faint">
          {tracks.length} track{tracks.length === 1 ? "" : "s"}
        </span>
      </div>
      <ol className="m-0 flex list-none flex-col gap-0 p-0">
        {tracks.map((track, index) => (
          <li
            key={`${track.position}-${index}`}
            className="grid grid-cols-[34px_1fr_auto] items-baseline gap-3 border-b border-line/60 py-1.5 text-[13px] last:border-b-0"
          >
            <span className="font-mono text-[11.5px] text-faint">{track.position}</span>
            <span className="min-w-0 text-body">{track.title}</span>
            <span className="font-mono text-[11.5px] tabular-nums text-dim">
              {track.length ?? ""}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ReviewPanel({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [review, setReview] = useState(item.review ?? "");
  useEffect(() => setReview(item.review ?? ""), [item.review]);
  const dirty = review !== (item.review ?? "");

  return (
    <div className="panel flex flex-col gap-3 p-5">
      <div className="paneltitle">Your review</div>
      <div className="text-[15px] tracking-[0.12em] text-accent">
        <RatingStars
          value={item.rating ? Number(item.rating) : 0}
          size={18}
          onChange={(value) => update.mutate({ rating: value })}
        />
      </div>
      <textarea
        value={review}
        onChange={(e) => setReview(e.target.value)}
        placeholder="What did you think?"
        rows={3}
        className="input w-full resize-y leading-relaxed"
      />
      {dirty && (
        <div className="flex justify-end">
          <button type="button" className="btn btn-sm" disabled={update.isPending} onClick={() => update.mutate({ review })}>
            Save review
          </button>
        </div>
      )}
    </div>
  );
}

const EVENT_LABEL: Record<string, string> = {
  item_added: "Added to collection",
  acquired: "Acquired — moved to backlog",
  item_deleted: "Removed",
};

/** "412.00"/412/null → "412"/null, for readable progress labels. */
function progressNumber(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isNaN(n) ? null : String(n);
}

function describeEvent(
  type: string,
  oldValue: Record<string, unknown> | null,
  newValue: Record<string, unknown> | null,
  unit: string | null = null,
): string {
  switch (type) {
    case "status_change":
      return `${labelOf(oldValue?.status)} → ${labelOf(newValue?.status)}`;
    case "progress_update": {
      const oldCurrent = progressNumber(oldValue?.progress_current);
      const newCurrent = progressNumber(newValue?.progress_current);
      const oldTotal = progressNumber(oldValue?.progress_total);
      const newTotal = progressNumber(newValue?.progress_total);
      if (oldCurrent === newCurrent && oldTotal !== newTotal) {
        return newTotal === null
          ? "Total cleared"
          : `Total set to ${newTotal}${unit ? ` ${unit}` : ""}`;
      }
      return `Progress ${oldCurrent ?? 0} → ${newCurrent ?? "?"}`;
    }
    case "rating_set":
      return newValue?.rating ? `Rated ${newValue.rating} ★` : "Rating cleared";
    case "loan_out":
      return `Lent to ${newValue?.borrowed_by ?? "someone"}`;
    case "loan_return":
      return `Returned by ${oldValue?.borrowed_by ?? "borrower"}`;
    case "season_watched":
      return `Season ${newValue?.season_number} ${newValue?.watched ? "watched" : "unwatched"}`;
    case "season_acquired":
      return `Season ${newValue?.season_number} acquired${newValue?.media ? ` (${newValue.media})` : ""}`;
    case "episode_watched":
      return `S${newValue?.season_number}E${newValue?.episode_number} ${
        newValue?.watched ? "watched" : "unwatched"
      }`;
    case "season_updated":
      return `Season ${newValue?.season_number} updated`;
    case "season_removed":
      return `Season ${oldValue?.season_number} removed`;
    default:
      return EVENT_LABEL[type] ?? type;
  }
}

function labelOf(status: unknown): string {
  return STATUS_LABEL[status as ItemStatus] ?? String(status ?? "?");
}

function ActivityPanel({ itemId, unit }: { itemId: string; unit: string | null }) {
  const { data } = useActivity(itemId);
  const del = useDeleteActivity(itemId);
  const [confirming, setConfirming] = useState<string | null>(null);
  const events = data?.events ?? [];
  return (
    <div className="panel flex flex-col gap-2.5 p-5">
      <div className="paneltitle">Activity</div>
      {events.slice(0, 12).map((event) => (
        <div key={event.id} className="group flex items-baseline gap-3 text-[12.5px]">
          <span className="whitespace-nowrap font-mono text-dim">
            {formatDate(event.created_at)}
          </span>
          <span className="min-w-0 flex-1 text-body">
            {describeEvent(event.event_type, event.old_value, event.new_value, unit)}
          </span>
          {confirming === event.id ? (
            <span className="flex flex-none items-center gap-2 text-xs">
              <button
                type="button"
                className="font-semibold text-danger"
                disabled={del.isPending}
                onClick={() =>
                  del.mutate(event.id, { onSettled: () => setConfirming(null) })
                }
              >
                Delete
              </button>
              <button type="button" className="text-muted" onClick={() => setConfirming(null)}>
                Keep
              </button>
            </span>
          ) : (
            <button
              type="button"
              aria-label="Delete this entry"
              title="Delete this entry"
              onClick={() => setConfirming(event.id)}
              className="grid h-7 w-7 flex-none place-items-center self-center rounded-md text-[16px] leading-none text-faint opacity-0 transition-opacity hover:bg-raised hover:text-danger focus-visible:opacity-100 group-hover:opacity-100 max-[820px]:opacity-70"
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

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

function DetailsPanel({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [relinking, setRelinking] = useState(false);
  const meta = item.metadata;
  const rows: Array<[string, React.ReactNode]> = [];
  // Books get their own editable row (see AuthorRow); other types would
  // only ever have an `authors` list from a legacy import.
  if (item.type !== "book" && Array.isArray(meta.authors) && meta.authors.length)
    rows.push(["Author", meta.authors.join(", ")]);
  if (typeof meta.artist === "string") rows.push(["Artist", meta.artist]);
  if (typeof meta.director === "string")
    rows.push([item.type === "tv" ? "Creator" : "Director", meta.director]);
  if (typeof meta.developer === "string") rows.push(["Developer", meta.developer]);
  if (item.platform)
    rows.push([
      "Platform",
      <Link
        to={`/?type=game&platform=${encodeURIComponent(item.platform)}`}
        className="text-accent no-underline hover:underline"
      >
        {item.platform}
      </Link>,
    ]);
  if (typeof meta.publisher === "string") rows.push(["Publisher", meta.publisher]);
  // A record is identified by its pressing, not just its title.
  if (typeof meta.label === "string") rows.push(["Label", meta.label]);
  if (typeof meta.catalog_number === "string")
    rows.push(["Catalogue number", <span className="font-mono">{meta.catalog_number}</span>]);
  if (typeof meta.release_type === "string") rows.push(["Release", meta.release_type]);
  if (item.type === "music" && typeof meta.country === "string")
    rows.push(["Pressed in", meta.country]);
  if (item.type === "music" && meta.track_count) rows.push(["Tracks", String(meta.track_count)]);
  const releaseDate = typeof meta.release_date === "string" ? meta.release_date : "";
  if (meta.year && !releaseDate) rows.push(["Year", String(meta.year)]);
  if (meta.page_count) rows.push(["Pages", String(meta.page_count)]);
  if (meta.runtime) rows.push(["Runtime", `${meta.runtime} min`]);
  if (item.type === "tv" && meta.number_of_seasons)
    rows.push(["Seasons", String(meta.number_of_seasons)]);
  if (item.type === "tv" && meta.number_of_episodes)
    rows.push(["Episodes", String(meta.number_of_episodes)]);
  if (item.type === "tv" && meta.episode_runtime)
    rows.push(["Episode runtime", `${meta.episode_runtime} min`]);
  if ((item.type === "movie" || item.type === "tv") && typeof meta.tmdb_rating === "number")
    rows.push(["TMDB rating", `${meta.tmdb_rating.toFixed(1)} / 10`]);
  if (typeof meta.isbn === "string") rows.push(["ISBN", meta.isbn]);
  const barcode = typeof meta.upc === "string" ? meta.upc : meta.barcode;
  if (typeof barcode === "string") rows.push(["Barcode", <span className="font-mono">{barcode}</span>]);
  if (item.format) rows.push(["Format", item.format]);
  if (item.purchase_price)
    rows.push(["Paid", `${currencySymbol(item.currency)} ${Number(item.purchase_price).toFixed(2)}`]);
  rows.push([
    "Added",
    formatDate(item.created_at),
  ]);

  // Game/movie/record release dates come from the provider and are facts —
  // only editable while still unknown (a music release date belongs to the
  // pressing, so re-linking is the way to change it). Books/TV vary by
  // edition, so they stay open.
  const lockedRelease =
    (item.type === "game" || item.type === "movie" || item.type === "music") &&
    Boolean(releaseDate);
  const showMedia = mediaOptions(item.type).length > 0 && item.format === "physical";
  const showStorefront = item.type === "game" && item.format === "digital";
  const media = typeof meta.media === "string" ? meta.media : "";
  const storefront = typeof meta.storefront === "string" ? meta.storefront : "";

  return (
    <div className="panel flex flex-col gap-2.5 p-4.5" style={{ padding: 18 }}>
      <div className="paneltitle">Details</div>
      {showMedia && (
        <MetaSelectRow
          label="Media"
          value={media}
          options={mediaOptions(item.type)}
          onChange={(value) => update.mutate({ metadata: { ...meta, media: value || undefined } })}
        />
      )}
      {showStorefront && (
        <MetaSelectRow
          label="Storefront"
          value={storefront}
          options={STOREFRONTS}
          onChange={(value) =>
            update.mutate({ metadata: { ...meta, storefront: value || undefined } })
          }
        />
      )}
      {lockedRelease ? (
        <div className="flex justify-between gap-3 border-b border-line/60 pb-2 text-[12.5px]">
          <span className="text-faint">Released</span>
          <span className="text-right font-medium text-text">
            {formatDate(releaseDate)}
          </span>
        </div>
      ) : (
      <div className="flex items-center justify-between gap-3 border-b border-line/60 pb-2 text-[12.5px]">
        <span className="text-faint">Released</span>
        <input
          type="date"
          aria-label="Release date"
          value={releaseDate}
          onChange={(e) => {
            const value = e.target.value;
            update.mutate({
              metadata: {
                ...meta,
                release_date: value || undefined,
                year: value ? Number(value.slice(0, 4)) : meta.year,
              },
            });
          }}
          className="input w-auto cursor-pointer px-2 py-1 text-right text-[12.5px] font-medium"
        />
      </div>
      )}
      {item.type === "book" && <AuthorRow item={item} />}
      {rows.map(([key, value]) => (
        <div key={key} className="flex justify-between gap-3 border-b border-line/60 pb-2 text-[12.5px] last:border-b-0 last:pb-0">
          <span className="text-faint">{key}</span>
          <span className="text-right font-medium capitalize text-text">{value}</span>
        </div>
      ))}
      {item.type !== "book" && (
        <div className="flex items-center justify-between gap-3 pt-1 text-[12.5px]">
          <span className="text-faint">Metadata</span>
          <button
            type="button"
            onClick={() => setRelinking(true)}
            className="font-semibold text-accent hover:underline"
          >
            Re-link…
          </button>
        </div>
      )}
      {relinking && <RelinkDialog item={item} onClose={() => setRelinking(false)} />}
    </div>
  );
}

/** Search the catalog and point this item at a different record — the
 * fix for a wrong or missing automatic metadata match. Rendered through
 * a portal: fixed positioning must anchor to the viewport, not to
 * whichever ancestor happens to gain a transform. */
function RelinkDialog({ item, onClose }: { item: Item; onClose: () => void }) {
  const [q, setQ] = useState(item.title);
  const search = useEnrichSearch(item.type, q);
  const relink = useRelinkItem(item.id);
  const results = search.data?.results ?? [];

  return createPortal(
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4"
      onClick={onClose}
    >
      {/* Capped to the visual viewport so the result list scrolls inside
          the dialog instead of pushing the buttons off small screens. */}
      <div
        className="panel flex max-h-[85dvh] w-full max-w-[440px] flex-col gap-3 p-5 shadow-lift"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="paneltitle">Re-link metadata</div>
        <p className="m-0 text-xs text-faint">
          Pick the matching {sourceLabel(item)} entry. Import info, playtime and your
          title are kept; description, cover and artwork come from the new match.
        </p>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search catalog"
          placeholder="Search…"
          className="input w-full"
        />
        <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
          {search.isLoading && <span className="px-2 py-1.5 text-xs text-faint">Searching…</span>}
          {results.map((result) => (
            <button
              key={result.external_id ?? result.title}
              type="button"
              disabled={relink.isPending || !result.external_id}
              onClick={() =>
                result.external_id &&
                relink.mutate(result.external_id, { onSuccess: onClose })
              }
              className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-raised disabled:opacity-50"
            >
              <span className="grid h-12 w-[34px] flex-none place-items-center overflow-hidden rounded-md border border-line-strong bg-surface">
                {result.cover_url && (
                  <img src={result.cover_url} alt="" className="h-full w-full object-cover" />
                )}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[13px] font-semibold">{result.title}</span>
                <span className="truncate text-xs text-faint">
                  {[
                    result.metadata.developer,
                    result.metadata.artist,
                    result.metadata.year,
                    result.metadata.media,
                    result.metadata.label,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
            </button>
          ))}
          {!search.isLoading && results.length === 0 && q.trim().length >= 2 && (
            <span className="px-2 py-1.5 text-xs text-faint">No matches.</span>
          )}
        </div>
        {relink.isError && (
          <p className="m-0 text-xs text-danger">{(relink.error as Error).message}</p>
        )}
        <button type="button" className="btn btn-ghost btn-sm w-fit" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>,
    document.body,
  );
}

/** The copies of this release you own more than once. They stay separate
 * items — own platform, format, status, progress — but the library shows
 * only the front one, and this panel is where you say which that is. */
function CopiesPanel({ item }: { item: Item }) {
  const { data } = useCopies(item.id);
  const front = useFrontCopy();
  const unbundle = useUnbundleCopy();
  const [picking, setPicking] = useState(false);
  const copies = data?.copies ?? [];
  const busy = front.isPending || unbundle.isPending;

  return (
    <div
      className="panel flex flex-col gap-2.5 p-4.5"
      style={{ padding: 18 }}
      role="group"
      aria-label="Copies"
    >
      <div className="paneltitle">Copies</div>
      {copies.length === 0 ? (
        <p className="m-0 text-[13px] text-faint">
          The only copy you have. Bundle another one to keep them under a single
          library entry.
        </p>
      ) : (
        copies.map((copy) =>
          copy.id === item.id ? (
            <div key={copy.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
              <span className="font-semibold">{copyLabel(copy)}</span>
              <span className="text-faint">· {STATUS_LABEL[copy.status]}</span>
              <span className="pillbadge border border-line-strong bg-raised text-muted">
                This copy
              </span>
              {copy.bundle_front && <span className="text-xs text-accent">In library</span>}
              <span className="ml-auto flex gap-2.5">
                {!copy.bundle_front && (
                  <button
                    type="button"
                    className="text-[12.5px] font-semibold text-accent"
                    disabled={busy}
                    onClick={() => front.mutate(copy.id)}
                  >
                    Show in library
                  </button>
                )}
                <button
                  type="button"
                  className="text-[12.5px] font-semibold text-muted"
                  disabled={busy}
                  onClick={() => unbundle.mutate(copy.id)}
                >
                  Unbundle
                </button>
              </span>
            </div>
          ) : (
            <Link
              key={copy.id}
              to={`/items/${copy.id}`}
              className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] no-underline text-inherit hover:text-accent"
            >
              <span className="font-semibold">{copyLabel(copy)}</span>
              <span className="text-faint">· {STATUS_LABEL[copy.status]}</span>
              {copy.bundle_front && <span className="text-xs text-accent">In library</span>}
            </Link>
          ),
        )
      )}
      <button
        type="button"
        className="btn btn-ghost btn-sm w-fit"
        onClick={() => setPicking(true)}
      >
        Bundle another copy…
      </button>
      {(front.isError || unbundle.isError) && (
        <p className="m-0 text-xs text-danger">
          {((front.error ?? unbundle.error) as Error).message}
        </p>
      )}
      {picking && (
        <BundleDialog item={item} copies={copies} onClose={() => setPicking(false)} />
      )}
    </div>
  );
}

/** Pick another copy out of your library. Only the same type can be
 * bundled, and copies already in this bundle are filtered out. */
function BundleDialog({
  item,
  copies,
  onClose,
}: {
  item: Item;
  copies: Item[];
  onClose: () => void;
}) {
  // The other copy is the same release, so its title is the same too — open
  // on it and let the field be edited for the odd re-titled copy.
  const [q, setQ] = useState(item.title);
  const search = useItems({ type: [item.type], q: q.trim() || undefined, sort: "title" });
  const bundleWith = useBundleWith(item.id);
  const own = new Set(copies.map((copy) => copy.id));
  const results = (search.data?.items ?? []).filter(
    (candidate) =>
      candidate.id !== item.id &&
      !own.has(candidate.id) &&
      // A collapsed row can stand for a copy of this very bundle.
      (item.bundle_id === null || candidate.bundle_id !== item.bundle_id),
  );

  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Bundle another copy"
        className="panel flex max-h-[85dvh] w-full max-w-[440px] flex-col gap-3 p-5 shadow-lift"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="paneltitle">Bundle another copy</div>
        <p className="m-0 text-xs text-faint">
          Pick the other copy of {item.title}. Both keep their own platform, format and
          progress; the library lists them as one entry.
        </p>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search your library"
          placeholder="Search your library…"
          className="input w-full"
        />
        <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
          {results.map((candidate) => (
            <button
              key={candidate.id}
              type="button"
              disabled={bundleWith.isPending}
              onClick={() => bundleWith.mutate([candidate.id], { onSuccess: onClose })}
              className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-raised disabled:opacity-50"
            >
              <span className="grid h-12 w-[34px] flex-none place-items-center overflow-hidden rounded-md border border-line-strong bg-surface">
                {candidate.cover_path && (
                  <img src={coverSrc(candidate)!} alt="" className="h-full w-full object-cover" />
                )}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[13px] font-semibold">{candidate.title}</span>
                <span className="truncate text-xs text-faint">
                  {copyLabel(candidate)} · {STATUS_LABEL[candidate.status]}
                  {candidate.bundle_count > 1 && ` · ${candidate.bundle_count} copies`}
                </span>
              </span>
            </button>
          ))}
          {!search.isLoading && results.length === 0 && (
            <span className="px-2 py-1.5 text-xs text-faint">
              No other {item.type} in your library matches.
            </span>
          )}
        </div>
        {bundleWith.isError && (
          <p className="m-0 text-xs text-danger">{(bundleWith.error as Error).message}</p>
        )}
        <button type="button" className="btn btn-ghost btn-sm w-fit" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>,
    document.body,
  );
}

function LoanPanel({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [name, setName] = useState("");
  const onLoan = Boolean(item.borrowed_by && !item.returned_date);

  if (onLoan) {
    return (
      <div
        className="flex flex-col gap-2 rounded-[14px] p-4.5"
        style={{
          padding: 18,
          background: "color-mix(in oklch, var(--accent) 7%, transparent)",
          border: "1px solid color-mix(in oklch, var(--accent) 25%, transparent)",
        }}
      >
        <div className="paneltitle">On loan</div>
        <div className="text-[13px] text-body">
          Currently with <strong>{item.borrowed_by}</strong>
          {item.loaned_date &&
            ` · since ${formatDate(item.loaned_date)}`}
        </div>
        <button
          type="button"
          className="w-fit text-[12.5px] font-semibold text-accent"
          disabled={update.isPending}
          onClick={() => update.mutate({ returned_date: new Date().toISOString().slice(0, 10) })}
        >
          Mark returned
        </button>
      </div>
    );
  }

  return (
    <div className="panel flex flex-col gap-2.5 p-4.5" style={{ padding: 18 }}>
      <div className="paneltitle">Loan</div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          update.mutate(
            { borrowed_by: name.trim(), loaned_date: new Date().toISOString().slice(0, 10), returned_date: null },
            { onSuccess: () => setName("") },
          );
        }}
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Lend to…"
          className="input min-w-0 flex-1 py-1.5"
        />
        <button type="submit" className="btn btn-ghost btn-sm" disabled={!name.trim()}>
          Lend out
        </button>
      </form>
      {item.returned_date && (
        <p className="m-0 text-xs text-faint">
          Returned by {item.borrowed_by} on{" "}
          {formatDate(item.returned_date)}
        </p>
      )}
    </div>
  );
}

function DangerZone({ item }: { item: Item }) {
  const del = useDeleteItem();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="flex flex-col gap-1.5 rounded-[14px] border border-dashed border-line-strong px-5 py-4">
      <div className="text-xs font-semibold text-muted">Danger zone</div>
      {confirming ? (
        <span className="flex flex-wrap items-center gap-2.5 text-[12.5px] text-muted">
          Delete “{item.title}” and its history?
          <button
            type="button"
            className="btn btn-sm"
            style={{ background: "var(--danger)", color: "#fff" }}
            onClick={() => del.mutate(item.id, { onSuccess: () => navigate("/") })}
          >
            Delete
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirming(false)}>
            Keep
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="w-fit text-[12.5px] font-semibold text-danger"
        >
          Remove from collection
        </button>
      )}
    </div>
  );
}

/** Inline editable metadata row used by Details (Media, Storefront). */
function MetaSelectRow({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line/60 pb-2 text-[12.5px]">
      <span className="text-faint">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input w-auto cursor-pointer appearance-none px-2 py-1 text-right text-[12.5px] font-medium"
      >
        <option value="">Choose…</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Tap-to-type author row for books. Open Library often has no author for
 * an edition (and manual entries can be saved without one), and books have
 * no Re-link to fix it with — so this stays editable, not just fillable.
 * Comma-separated, matching how the add form takes authors. */
function AuthorRow({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [editing, setEditing] = useState(false);
  const authors = Array.isArray(item.metadata.authors)
    ? (item.metadata.authors as unknown[]).filter((a): a is string => typeof a === "string")
    : [];
  const shown = authors.join(", ");

  const save = (value: string) => {
    setEditing(false);
    const names = value.split(",").map((name) => name.trim()).filter(Boolean);
    if (names.join(", ") === shown) return; // no-op: don't PATCH
    // Cleared → the key drops out of the metadata (JSON.stringify skips it).
    update.mutate({
      metadata: { ...item.metadata, authors: names.length ? names : undefined },
    });
  };

  return (
    <div className="flex items-center justify-between gap-3 border-b border-line/60 pb-2 text-[12.5px]">
      <span className="flex-none text-faint">Author</span>
      {editing ? (
        <input
          autoFocus
          aria-label="Author"
          defaultValue={shown}
          placeholder="Who wrote it?"
          onBlur={(e) => save(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          className="input min-w-0 flex-1 px-2 py-1 text-right text-[12.5px] font-medium"
        />
      ) : (
        <button
          type="button"
          aria-label="Edit author"
          title="Tap to type the author"
          onClick={() => setEditing(true)}
          className={`min-w-0 text-right font-medium underline decoration-dotted hover:text-accent ${
            shown ? "text-text" : "text-faint"
          }`}
        >
          {shown || "Add author…"}
        </button>
      )}
    </div>
  );
}

/** Replace the cover: photo/file upload, or fetch from a pasted URL. */
function CoverEditor({ item }: { item: Item }) {
  const uploadCover = useUploadCover(item.id);
  const update = useUpdateItem(item.id);
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const busy = uploadCover.isPending || update.isPending;
  const error = (uploadCover.error ?? update.error) as Error | null;

  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-fit text-[11px] font-medium text-faint hover:text-text"
      >
        {item.cover_path ? "Change cover" : "Add cover"}
      </button>
      {open && (
        <div className="panel flex flex-col gap-2 p-2.5">
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) uploadCover.mutate(file, { onSuccess: () => setOpen(false) });
            }}
          />
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            {uploadCover.isPending ? "Uploading…" : "Upload photo"}
          </button>
          <form
            className="flex flex-col gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              if (!url.trim()) return;
              update.mutate(
                { cover_url: url.trim() },
                {
                  onSuccess: () => {
                    setUrl("");
                    setOpen(false);
                  },
                },
              );
            }}
          >
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="…or paste an image URL"
              className="input w-full px-2 py-1.5 text-[11.5px]"
            />
            {url.trim() && (
              <button type="submit" className="btn btn-sm" disabled={busy}>
                {update.isPending ? "Fetching…" : "Use this URL"}
              </button>
            )}
          </form>
          {error && <p className="m-0 text-[11px] text-danger">{error.message}</p>}
        </div>
      )}
    </div>
  );
}

function currencySymbol(code: string | null): string {
  return code === "EUR" ? "€" : code === "USD" ? "$" : code === "GBP" ? "£" : (code ?? "");
}
