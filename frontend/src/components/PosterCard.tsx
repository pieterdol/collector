/** Poster card, graphite design: cover with a status badge on the art,
 * caption below (title, meta line, stars in accent). */

import { Link } from "react-router-dom";
import type { Item, ItemStatus } from "../lib/types";
import { STATUS_LABEL } from "../lib/types";
import { MediaBadge } from "./MediaBadge";
import { RatingStars } from "./RatingStars";

const STATUS_COLOR: Record<ItemStatus, string> = {
  wishlist: "var(--muted)",
  backlog: "var(--muted)",
  in_progress: "var(--accent)",
  completed: "var(--done)",
  abandoned: "var(--dim)",
};

function progressPercent(item: Item): number | null {
  if (!item.progress_current || !item.progress_total) return null;
  const pct = (Number(item.progress_current) / Number(item.progress_total)) * 100;
  return Number.isFinite(pct) ? Math.min(100, Math.round(pct)) : null;
}

/** Cover URL versioned by updated_at, so replaced covers bypass caches. */
export function coverSrc(item: Item): string | null {
  if (!item.cover_path) return null;
  return `${item.cover_path}?v=${Date.parse(item.updated_at)}`;
}

export function describeItem(item: Item): string {
  const meta = item.metadata;
  const parts: string[] = [];
  if (Array.isArray(meta.authors) && meta.authors.length) parts.push(String(meta.authors[0]));
  if (typeof meta.artist === "string") parts.push(meta.artist);
  if (typeof meta.director === "string") parts.push(meta.director);
  if (typeof meta.developer === "string") parts.push(meta.developer);
  if (item.platform && !meta.developer) parts.push(item.platform);
  if (meta.year) parts.push(String(meta.year));
  return parts.slice(0, 2).join(" · ");
}

export function PosterCard({ item }: { item: Item }) {
  const pct = progressPercent(item);
  const onLoan = Boolean(item.borrowed_by && !item.returned_date);

  return (
    <Link to={`/items/${item.id}`} className="cardlink">
      <div className="poster">
        {item.cover_path ? (
          <img src={coverSrc(item)!} alt="" loading="lazy" />
        ) : (
          <span className="px-3 text-center font-mono text-[10.5px] tracking-[0.04em] text-text/45">
            {item.title}
          </span>
        )}
        <span className="badge" style={{ color: STATUS_COLOR[item.status] }}>
          {STATUS_LABEL[item.status]}
        </span>
        {onLoan && <span className="badge badge-loan">→ {item.borrowed_by}</span>}
        <MediaBadge item={item} />
        {pct !== null && item.status === "in_progress" && (
          <div className="pstrip" title={`${item.progress_current} / ${item.progress_total}`}>
            <i style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
      <div className="flex flex-col gap-0.5">
        <div className="truncate text-[13.5px] font-semibold leading-[1.3]">{item.title}</div>
        <div className="truncate text-xs text-faint">{describeItem(item)}</div>
        {item.rating && (
          <div className="text-xs tracking-[0.1em] text-accent">
            <RatingStars value={Number(item.rating)} size={11} />
          </div>
        )}
      </div>
    </Link>
  );
}
