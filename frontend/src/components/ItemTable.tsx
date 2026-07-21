/** Dense table view, graphite design: grid rows inside one surface card. */

import { useNavigate } from "react-router-dom";
import { formatDate } from "../lib/dates";
import type { Item, ItemStatus } from "../lib/types";
import { STATUS_LABEL } from "../lib/types";
import { RatingStars } from "./RatingStars";

const COLUMNS = "grid-cols-[2.2fr_0.8fr_0.9fr_1fr_0.9fr_0.8fr]";

const STATUS_COLOR: Record<ItemStatus, string> = {
  wishlist: "var(--muted)",
  backlog: "var(--muted)",
  in_progress: "var(--accent)",
  completed: "var(--done)",
  abandoned: "var(--dim)",
};

export function ItemTable({ items }: { items: Item[] }) {
  const navigate = useNavigate();
  return (
    <section className="panel overflow-x-auto">
      <div className="min-w-[720px]">
        <div
          className={`grid ${COLUMNS} gap-3 border-b border-line px-4.5 py-3 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-faint`}
          style={{ paddingLeft: 18, paddingRight: 18 }}
        >
          <span>Title</span>
          <span>Type</span>
          <span>Format</span>
          <span>Status</span>
          <span>Rating</span>
          <span>Added</span>
        </div>
        {items.map((item) => (
          <div
            key={item.id}
            onClick={() => navigate(`/items/${item.id}`)}
            className={`grid ${COLUMNS} cursor-pointer items-center gap-3 border-b border-line/60 px-4.5 py-3 text-[13px] transition-colors last:border-b-0 hover:bg-raised/40`}
            style={{ paddingLeft: 18, paddingRight: 18 }}
          >
            <span className="truncate font-semibold">{item.title}</span>
            <span className="text-xs font-semibold capitalize" style={{ color: `var(--${item.type})` }}>
              {item.type}
            </span>
            <span className="font-mono text-xs capitalize text-muted">{item.format ?? "—"}</span>
            <span className="text-xs font-semibold" style={{ color: STATUS_COLOR[item.status] }}>
              {STATUS_LABEL[item.status]}
            </span>
            <span>
              {item.rating ? (
                <span className="text-accent">
                  <RatingStars value={Number(item.rating)} size={11} />
                </span>
              ) : (
                <span className="font-mono text-xs text-dim">—</span>
              )}
            </span>
            <span className="font-mono text-xs tabular-nums text-muted">
              {formatDate(item.created_at)}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
