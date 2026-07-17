/** Item detail — a full page (not a panel): poster, meta, progress,
 * rating/review, loan tracking and the activity timeline. */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AcquireDialog } from "../components/AcquireDialog";
import { BackIcon } from "../components/icons";
import { coverColors } from "../components/PosterCard";
import { RatingStars } from "../components/RatingStars";
import { DetailSkeleton } from "../components/Skeletons";
import { useActivity, useDeleteItem, useItem, useUpdateItem } from "../lib/queries";
import type { Item, ItemStatus } from "../lib/types";
import { STATUS_LABEL, progressUnit } from "../lib/types";

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

function BackLink() {
  return (
    <Link
      to="/"
      className="mb-5 inline-flex items-center gap-2 rounded-full bg-surface px-3.5 py-2 text-[13px] font-semibold text-muted no-underline transition-colors hover:bg-raised hover:text-text"
    >
      <BackIcon /> Shelf
    </Link>
  );
}

function Detail({ item }: { item: Item }) {
  const [c1, c2] = coverColors(item.title);
  const update = useUpdateItem(item.id);
  const [acquiring, setAcquiring] = useState(false);

  const meta = item.metadata;
  const metaRow: string[] = [];
  if (meta.page_count) metaRow.push(`${meta.page_count} pages`);
  if (meta.runtime) metaRow.push(`${meta.runtime} min`);
  if (meta.year) metaRow.push(String(meta.year));
  if (meta.isbn) metaRow.push(`ISBN ${meta.isbn}`);
  if (item.purchase_price)
    metaRow.push(
      `${currencySymbol(item.currency)} ${Number(item.purchase_price).toFixed(2)}` +
        (item.acquisition_date ? ` · ${formatDate(item.acquisition_date)}` : ""),
    );

  const chips = [
    ...(Array.isArray(meta.authors) ? meta.authors.map(String) : []),
    ...(typeof meta.director === "string" ? [meta.director] : []),
    ...(typeof meta.developer === "string" ? [meta.developer] : []),
    ...(typeof meta.publisher === "string" ? [meta.publisher] : []),
    ...(typeof meta.platform === "string" ? [meta.platform] : []),
  ].filter(Boolean);

  return (
    <section>
      <BackLink />
      <div className="relative overflow-hidden rounded-2xl p-10 max-[760px]:p-5">
        {/* soft glow from the cover colors, fading into the page */}
        <div
          aria-hidden
          className="absolute inset-0 scale-[1.4] opacity-40 blur-[70px]"
          style={{ background: `linear-gradient(165deg, ${c1}, ${c2})` }}
        />
        <div
          aria-hidden
          className="absolute inset-0"
          style={{ background: "linear-gradient(to bottom, transparent 30%, var(--bg) 100%)" }}
        />

        <div className="relative z-10 grid grid-cols-[280px_1fr] items-start gap-9 max-[760px]:grid-cols-1">
          <div
            className="poster max-[760px]:max-w-[240px]"
            style={{ "--c1": c1, "--c2": c2 } as React.CSSProperties}
          >
            {item.cover_path ? (
              <img src={item.cover_path} alt={`Cover of ${item.title}`} />
            ) : (
              <div className="relative p-5 pb-6">
                <div className="text-[30px] font-extrabold leading-[1.05] tracking-tight text-white/95 [text-wrap:balance]">
                  {item.title}
                </div>
              </div>
            )}
          </div>

          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: `var(--${item.type})` }} />
              {item.type}
              {item.format && ` · ${item.format}`}
              <span className="text-faint">· Added {formatDate(item.created_at)}</span>
            </div>
            <h1 className="m-0 mb-2.5 text-[clamp(28px,4vw,44px)] font-extrabold leading-[1.03] tracking-tight [text-wrap:balance]">
              {item.title}
            </h1>
            {metaRow.length > 0 && (
              <div className="mb-4 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[13px] tabular-nums text-muted">
                {metaRow.map((entry) => (
                  <span key={entry}>{entry}</span>
                ))}
              </div>
            )}
            {chips.length > 0 && (
              <div className="mb-6 flex flex-wrap gap-2">
                {chips.map((chip) => (
                  <span key={chip} className="rounded-full bg-surface px-3.5 py-1.5 text-[13px] font-semibold text-muted">
                    {chip}
                  </span>
                ))}
              </div>
            )}

            <StatusRow item={item} onAcquire={() => setAcquiring(true)} />

            <div className="mt-4 grid grid-cols-2 gap-4 max-[900px]:grid-cols-1">
              {progressUnit(item.type) && item.status !== "wishlist" && (
                <ProgressPanel item={item} />
              )}
              <RatingPanel item={item} />
              {item.status !== "wishlist" && <LoanPanel item={item} />}
              <ActivityPanel itemId={item.id} />
            </div>

            <DangerZone item={item} />
            {update.isError && (
              <p className="mt-3 text-[13px] text-movie">{(update.error as Error).message}</p>
            )}
          </div>
        </div>
      </div>
      {acquiring && <AcquireDialog item={item} onClose={() => setAcquiring(false)} />}
    </section>
  );
}

function StatusRow({ item, onAcquire }: { item: Item; onAcquire: () => void }) {
  const update = useUpdateItem(item.id);
  if (item.status === "wishlist") {
    return (
      <div className="flex items-center gap-3">
        <span className="rounded-full border border-dashed border-accent/60 px-3.5 py-1.5 text-[13px] font-semibold text-muted">
          On your wishlist
        </span>
        <button type="button" className="btn btn-go btn-sm" onClick={onAcquire}>
          Mark as acquired
        </button>
      </div>
    );
  }
  const statuses: ItemStatus[] = ["backlog", "in_progress", "completed", "abandoned"];
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Status">
      {statuses.map((status) => (
        <button
          key={status}
          type="button"
          className="pill"
          aria-pressed={item.status === status}
          onClick={() => item.status !== status && update.mutate({ status })}
        >
          {STATUS_LABEL[status]}
        </button>
      ))}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-surface p-5">
      <h4 className="m-0 mb-3.5 font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-faint">
        {title}
      </h4>
      {children}
    </div>
  );
}

function ProgressPanel({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const unit = progressUnit(item.type)!;
  const current = item.progress_current ? Number(item.progress_current) : 0;
  const total = item.progress_total ? Number(item.progress_total) : null;
  const pct = total ? Math.min(100, Math.round((current / total) * 100)) : null;
  const [editingTotal, setEditingTotal] = useState(false);
  const step = unit === "pages" ? 10 : 1;

  function setCurrent(value: number) {
    const clamped = Math.max(0, total !== null ? Math.min(value, total) : value);
    update.mutate({ progress_current: clamped });
  }

  return (
    <Panel title={unit === "pages" ? "Reading progress" : "Play time"}>
      <div className="flex items-center gap-3.5">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
          {pct !== null && <div className="h-full rounded-full bg-go" style={{ width: `${pct}%` }} />}
        </div>
        <span className="font-mono text-[11.5px] tabular-nums text-muted">
          {current}
          {total !== null && ` / ${total}`} {unit === "pages" ? "pp" : "h"}
          {pct !== null && ` · ${pct}%`}
        </span>
        <div className="flex rounded-full bg-raised">
          <button
            type="button"
            aria-label={`${step} ${unit} less`}
            onClick={() => setCurrent(current - step)}
            className="rounded-full px-3 py-1 font-mono text-sm text-muted hover:bg-line hover:text-text"
          >
            −
          </button>
          <button
            type="button"
            aria-label={`${step} ${unit} more`}
            onClick={() => setCurrent(current + step)}
            className="rounded-full px-3 py-1 font-mono text-sm text-muted hover:bg-line hover:text-text"
          >
            +
          </button>
        </div>
      </div>
      <p className="m-0 mt-3 text-xs text-faint">
        {editingTotal ? (
          <input
            autoFocus
            type="number"
            defaultValue={total ?? ""}
            onBlur={(e) => {
              setEditingTotal(false);
              const value = e.target.value ? Number(e.target.value) : null;
              if (value !== total) update.mutate({ progress_total: value });
            }}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            className="w-24 rounded border-none bg-raised px-2 py-1 text-xs text-text outline-none"
          />
        ) : (
          <button type="button" className="text-faint underline decoration-dotted" onClick={() => setEditingTotal(true)}>
            {total !== null ? `total: ${total} ${unit}` : `set total ${unit}`}
          </button>
        )}
      </p>
    </Panel>
  );
}

function RatingPanel({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [review, setReview] = useState(item.review ?? "");
  useEffect(() => setReview(item.review ?? ""), [item.review]);
  const dirty = review !== (item.review ?? "");

  return (
    <Panel title="Your rating">
      <RatingStars
        value={item.rating ? Number(item.rating) : 0}
        size={24}
        onChange={(value) => update.mutate({ rating: value })}
      />
      <textarea
        value={review}
        onChange={(e) => setReview(e.target.value)}
        placeholder="What did you think?"
        rows={3}
        className="mt-3 w-full resize-y rounded-lg border border-line bg-raised px-3.5 py-2.5 text-[13.5px] leading-relaxed outline-none focus:border-accent"
      />
      {dirty && (
        <div className="mt-2 flex justify-end">
          <button
            type="button"
            className="btn btn-sm"
            disabled={update.isPending}
            onClick={() => update.mutate({ review })}
          >
            Save review
          </button>
        </div>
      )}
    </Panel>
  );
}

function LoanPanel({ item }: { item: Item }) {
  const update = useUpdateItem(item.id);
  const [name, setName] = useState("");
  const onLoan = item.borrowed_by && !item.returned_date;

  return (
    <Panel title="Loan">
      {onLoan ? (
        <div className="flex items-center justify-between gap-2.5 text-[13.5px]">
          <span>
            Lent to <b>{item.borrowed_by}</b>
            {item.loaned_date && ` · ${formatDate(item.loaned_date)}`}
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => update.mutate({ returned_date: today() })}
          >
            Mark returned
          </button>
        </div>
      ) : (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim()) return;
            update.mutate(
              { borrowed_by: name.trim(), loaned_date: today(), returned_date: null },
              { onSuccess: () => setName("") },
            );
          }}
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Lend to…"
            className="min-w-0 flex-1 rounded-lg border border-line bg-raised px-3.5 py-2 text-[13.5px] outline-none focus:border-accent"
          />
          <button type="submit" className="btn btn-ghost btn-sm" disabled={!name.trim()}>
            Lend out
          </button>
        </form>
      )}
      {item.returned_date && (
        <p className="m-0 mt-2.5 text-xs text-faint">
          Returned by {item.borrowed_by} on {formatDate(item.returned_date)}
        </p>
      )}
    </Panel>
  );
}

const EVENT_LABEL: Record<string, string> = {
  item_added: "Added to shelf",
  status_change: "Status",
  progress_update: "Progress",
  rating_set: "Rated",
  acquired: "Acquired",
  loan_out: "Lent out",
  loan_return: "Returned",
};

function ActivityPanel({ itemId }: { itemId: string }) {
  const { data } = useActivity(itemId);
  const events = data?.events ?? [];
  return (
    <Panel title="Activity">
      <ul className="m-0 list-none p-0">
        {events.slice(0, 8).map((event) => (
          <li key={event.id} className="flex items-baseline gap-3 py-1.5 text-[12.5px] text-muted">
            <span className="w-[74px] flex-none font-mono text-[10.5px] tabular-nums text-faint">
              {formatDate(event.created_at)}
            </span>
            <span
              className="relative top-[-1px] h-1.5 w-1.5 flex-none rounded-full"
              style={{
                background:
                  event.event_type === "status_change" || event.event_type === "acquired"
                    ? "var(--go)"
                    : event.event_type === "item_added"
                      ? "var(--faint)"
                      : "var(--accent)",
              }}
            />
            <span className="min-w-0">{describeEvent(event.event_type, event.old_value, event.new_value)}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function describeEvent(
  type: string,
  oldValue: Record<string, unknown> | null,
  newValue: Record<string, unknown> | null,
): string {
  switch (type) {
    case "status_change":
      return `${labelOf(oldValue?.status)} → ${labelOf(newValue?.status)}`;
    case "progress_update":
      return `Progress ${oldValue?.progress_current ?? 0} → ${newValue?.progress_current ?? "?"}`;
    case "rating_set":
      return newValue?.rating ? `Rated ${newValue.rating} ★` : "Rating cleared";
    case "loan_out":
      return `Lent to ${newValue?.borrowed_by ?? "someone"}`;
    case "loan_return":
      return `Returned by ${oldValue?.borrowed_by ?? "borrower"}`;
    case "acquired":
      return "Acquired — moved to backlog";
    default:
      return EVENT_LABEL[type] ?? type;
  }
}

function labelOf(status: unknown): string {
  return STATUS_LABEL[status as ItemStatus] ?? String(status ?? "?");
}

function DangerZone({ item }: { item: Item }) {
  const del = useDeleteItem();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="mt-5 flex justify-end">
      {confirming ? (
        <span className="flex items-center gap-2.5 text-[13px] text-muted">
          Delete “{item.title}” and its history?
          <button
            type="button"
            className="btn btn-sm"
            style={{ background: "var(--movie)" }}
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
          className="text-[12.5px] text-faint underline decoration-dotted hover:text-movie"
        >
          Remove from collection
        </button>
      )}
    </div>
  );
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { day: "2-digit", month: "short" });
}

function currencySymbol(code: string | null): string {
  return code === "EUR" ? "€" : code === "USD" ? "$" : code === "GBP" ? "£" : (code ?? "");
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}
