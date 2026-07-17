/** Flat poster card: cover art is the card; caption sits quietly below. */

import { Link } from "react-router-dom";
import type { Item } from "../lib/types";
import { RatingStars } from "./RatingStars";

/** Deterministic gradient for items without a stored cover. */
export function coverColors(title: string): [string, string] {
  let hash = 0;
  for (const ch of title) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  const hue = ((hash % 360) + 360) % 360;
  return [`oklch(0.45 0.09 ${hue})`, `oklch(0.22 0.06 ${(hue + 40) % 360})`];
}

function progressPercent(item: Item): number | null {
  if (!item.progress_current || !item.progress_total) return null;
  const pct = (Number(item.progress_current) / Number(item.progress_total)) * 100;
  return Number.isFinite(pct) ? Math.min(100, Math.round(pct)) : null;
}

export function PosterCard({ item }: { item: Item }) {
  const [c1, c2] = coverColors(item.title);
  const pct = progressPercent(item);
  const sub = describeItem(item);

  return (
    <Link to={`/items/${item.id}`} className="group block no-underline text-inherit">
      <div className="poster" style={{ "--c1": c1, "--c2": c2 } as React.CSSProperties}>
        {item.cover_path ? (
          <img src={item.cover_path} alt="" loading="lazy" />
        ) : (
          <div className="relative p-3.5 pb-4">
            <div className="font-extrabold leading-tight tracking-tight text-[17px] text-white/95 [text-wrap:balance]">
              {item.title}
            </div>
            {sub && (
              <div className="mt-1 font-mono text-[9.5px] uppercase tracking-[0.12em] text-white/70">
                {sub}
              </div>
            )}
          </div>
        )}
        {item.status === "in_progress" && pct !== null && (
          <span className="badge">
            <i />
            {pct}%
          </span>
        )}
        {item.borrowed_by && !item.returned_date && (
          <span className="badge badge-loan">
            <i />
            {item.borrowed_by}
          </span>
        )}
        {pct !== null && (
          <div className="pstrip" title={`${item.progress_current} / ${item.progress_total}`}>
            <i style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
      <div className="px-1 pt-2">
        <div className="truncate text-[13px] font-semibold">{item.title}</div>
        <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-faint">
          <span
            className="h-[5px] w-[5px] flex-none rounded-full"
            style={{ background: `var(--${item.type})` }}
          />
          <span>{item.format ?? item.type}</span>
          {item.rating && (
            <span className="ml-auto">
              <RatingStars value={Number(item.rating)} size={10} />
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

function describeItem(item: Item): string {
  const meta = item.metadata;
  const parts: string[] = [];
  if (Array.isArray(meta.authors) && meta.authors.length) parts.push(String(meta.authors[0]));
  if (typeof meta.director === "string") parts.push(meta.director);
  if (typeof meta.developer === "string") parts.push(meta.developer);
  if (meta.year) parts.push(String(meta.year));
  return parts.slice(0, 2).join(" · ");
}
