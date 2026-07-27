/** Stats: tiles, Continue, Out on loan, Recent activity — all served by
 * /api/stats, which is pure queries over the activity-event log. */

import { Link } from "react-router-dom";
import { formatDate } from "../lib/dates";
import { useStats } from "../lib/queries";
import type { Stats } from "../lib/types";

export default function StatsPage() {
  const { data, isLoading } = useStats();

  if (isLoading || !data) {
    return (
      <section className="grid grid-cols-4 gap-3.5 max-[820px]:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="skeleton h-28" />
        ))}
      </section>
    );
  }

  const { book, movie, tv, game, music, value } = data.tiles;
  const symbol = value.currency === "EUR" ? "€" : value.currency === "USD" ? "$" : value.currency;

  return (
    <>
      <section className="grid grid-cols-4 gap-3.5 max-[980px]:grid-cols-2 max-[480px]:grid-cols-1">
        <Tile
          dot="var(--book)"
          label="Books"
          number={book.total}
          sub={`${book.in_progress} in progress · ${book.completed_this_year} read this year`}
        />
        <Tile
          dot="var(--movie)"
          label="Movies"
          number={movie.total}
          sub={`${movie.physical} physical · ${movie.digital} digital`}
        />
        <Tile
          dot="var(--tv)"
          label="TV"
          number={tv.total}
          sub={`${tv.physical} physical · ${tv.digital} digital`}
        />
        <Tile
          dot="var(--game)"
          label="Games"
          number={game.total}
          sub={`${game.via_steam} via Steam · ${formatHours(game.hours_played)} played`}
        />
        <Tile
          dot="var(--music)"
          label="Music"
          number={music.total}
          sub={`${music.vinyl} vinyl · ${music.cd} CD`}
        />
        <Tile
          dot="var(--nav-dot)"
          label="Collection value"
          number={`${symbol}${formatMoney(value.total)}`}
          sub={Number(value.this_month) > 0 ? `+ ${symbol}${formatMoney(value.this_month)} this month` : "nothing this month"}
        />
      </section>

      <section className="grid grid-cols-[2fr_1fr_1fr] items-start gap-3.5 max-[980px]:grid-cols-1">
        <ContinuePanel entries={data.continue} />
        <LoansPanel loans={data.loans} />
        <RecentPanel recent={data.recent} />
      </section>
    </>
  );
}

function Tile({ dot, label, number, sub }: { dot: string; label: string; number: number | string; sub: string }) {
  return (
    <div className="panel flex flex-col gap-1.5 px-5 py-4.5" style={{ paddingTop: 18, paddingBottom: 18 }}>
      <div className="flex items-center gap-2 text-[12.5px] font-semibold uppercase tracking-[0.06em] text-muted">
        <span className="h-2 w-2 rounded-[2px]" style={{ background: dot }} /> {label}
      </div>
      <div className="font-display text-[32px] font-bold leading-tight">{number}</div>
      <div className="text-[12.5px] text-faint">{sub}</div>
    </div>
  );
}

function ContinuePanel({ entries }: { entries: Stats["continue"] }) {
  return (
    <div className="panel flex flex-col gap-3.5 px-5 py-4.5" style={{ paddingTop: 18, paddingBottom: 18 }}>
      <div className="flex items-baseline gap-2">
        <span className="paneltitle">Continue</span>
        <span className="text-xs text-faint">{entries.length} in progress</span>
      </div>
      {entries.length === 0 && <p className="m-0 text-[13px] text-faint">Nothing in progress right now.</p>}
      <div className="flex flex-col gap-3">
        {entries.map((entry) => (
          <Link key={entry.id} to={`/items/${entry.id}`} className="no-underline text-inherit">
            <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
              <div className="truncate text-[13.5px] font-semibold">
                {entry.title}
                {entry.sub && <span className="font-normal text-faint"> · {entry.sub}</span>}
              </div>
              <div className="font-mono text-xs tabular-nums" style={{ color: `var(--${entry.type})` }}>
                {entry.type === "book"
                  ? `p. ${entry.progress_current ?? 0}${entry.progress_total ? ` / ${entry.progress_total}` : ""}`
                  : `${entry.progress_current ?? 0} h`}
              </div>
              {entry.type === "book" && entry.pct !== null && (
                <div className="col-span-2 h-[5px] overflow-hidden rounded-[3px]" style={{ background: "var(--line)" }}>
                  <div
                    className="h-full rounded-[3px]"
                    style={{ width: `${entry.pct}%`, background: `var(--${entry.type})` }}
                  />
                </div>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function LoansPanel({ loans }: { loans: Stats["loans"] }) {
  return (
    <div className="panel flex flex-col gap-3 px-5 py-4.5" style={{ paddingTop: 18, paddingBottom: 18 }}>
      <div className="paneltitle">Out on loan</div>
      {loans.length === 0 && <p className="m-0 text-[13px] text-faint">Everything is home.</p>}
      {loans.map((loan) => (
        <Link key={loan.id} to={`/items/${loan.id}`} className="flex flex-col gap-0.5 no-underline text-inherit">
          <span className="text-[13px] font-semibold">{loan.title}</span>
          <span className="text-xs text-faint">
            {loan.borrowed_by}
            {loan.loaned_date &&
              ` · since ${formatDate(loan.loaned_date)}`}
          </span>
        </Link>
      ))}
    </div>
  );
}

function RecentPanel({ recent }: { recent: Stats["recent"] }) {
  return (
    <div className="panel flex flex-col gap-2.5 px-5 py-4.5" style={{ paddingTop: 18, paddingBottom: 18 }}>
      <div className="paneltitle">Recent activity</div>
      {recent.length === 0 && <p className="m-0 text-[13px] text-faint">No activity yet.</p>}
      {recent.map((event, index) => (
        <div key={index} className="flex items-baseline gap-2 text-[12.5px] text-body">
          <span style={{ color: `var(--${event.type})` }}>●</span>
          <Link to={`/items/${event.item_id}`} className="min-w-0 truncate no-underline text-inherit">
            {summarize(event)}
          </Link>
        </div>
      ))}
    </div>
  );
}

function summarize(event: Stats["recent"][number]): React.ReactNode {
  const title = <strong>{event.title}</strong>;
  switch (event.event_type) {
    case "item_added":
      return <>Added {title}</>;
    case "status_change":
      return event.new_value?.status === "completed" ? <>Finished {title}</> : <>{title} → {String(event.new_value?.status ?? "").replace("_", " ")}</>;
    case "progress_update":
      return <>Progress in {title}</>;
    case "rating_set":
      return <>Rated {title} {event.new_value?.rating ? `★${event.new_value.rating}` : ""}</>;
    case "acquired":
      return <>Acquired {title}</>;
    case "loan_out":
      return <>Lent {title} to {String(event.new_value?.borrowed_by ?? "")}</>;
    case "loan_return":
      return <>{title} returned</>;
    case "season_watched":
      return event.new_value?.watched
        ? <>Watched {title} S{String(event.new_value?.season_number ?? "?")}</>
        : title;
    case "season_acquired":
      return <>Acquired {title} S{String(event.new_value?.season_number ?? "?")}</>;
    default:
      return title;
  }
}

function formatHours(hours: number): string {
  return `${Math.round(hours).toLocaleString()} h`;
}

function formatMoney(value: string): string {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
}
