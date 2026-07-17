/** Dense table view of the collection. */

import { useNavigate } from "react-router-dom";
import type { Item } from "../lib/types";
import { STATUS_LABEL } from "../lib/types";
import { coverColors } from "./PosterCard";
import { RatingStars } from "./RatingStars";

export function ItemTable({ items }: { items: Item[] }) {
  const navigate = useNavigate();
  return (
    <div className="overflow-x-auto rounded-xl bg-surface">
      <table className="w-full min-w-[760px] border-collapse text-[13.5px]">
        <thead>
          <tr>
            {["Title", "Medium", "Format", "Status", "Progress", "Rating", "Added"].map((h) => (
              <th
                key={h}
                className="border-b border-line px-4 py-3 text-left font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-faint"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <Row key={item.id} item={item} onOpen={() => navigate(`/items/${item.id}`)} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ item, onOpen }: { item: Item; onOpen: () => void }) {
  const [c1, c2] = coverColors(item.title);
  const progress =
    item.progress_current && item.progress_total
      ? `${Number(item.progress_current)}/${Number(item.progress_total)}`
      : "—";
  return (
    <tr
      onClick={onOpen}
      className="cursor-pointer transition-colors last:border-none hover:bg-raised"
    >
      <td className="border-b border-line-soft px-4 py-2.5">
        <span className="flex items-center gap-3 font-semibold">
          <span
            className="h-10 w-7 flex-none overflow-hidden rounded-[5px]"
            style={{ background: `linear-gradient(165deg, ${c1}, ${c2})` }}
          >
            {item.cover_path && (
              <img src={item.cover_path} alt="" className="h-full w-full object-cover" />
            )}
          </span>
          {item.title}
        </span>
      </td>
      <td className="border-b border-line-soft px-4 py-2.5">
        <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em]" style={{ color: `var(--${item.type})` }}>
          <span className="h-[5px] w-[5px] rounded-full" style={{ background: `var(--${item.type})` }} />
          {item.type}
        </span>
      </td>
      <td className="border-b border-line-soft px-4 py-2.5 font-mono text-xs text-muted">
        {item.format ?? "—"}
      </td>
      <td className="border-b border-line-soft px-4 py-2.5">
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-semibold ${
            item.status === "completed" ? "text-go" : item.status === "in_progress" ? "text-text" : "text-muted"
          }`}
        >
          <i
            className="h-1.5 w-1.5 rounded-full"
            style={{
              background:
                item.status === "completed" || item.status === "in_progress"
                  ? "var(--go)"
                  : "var(--faint)",
            }}
          />
          {STATUS_LABEL[item.status]}
        </span>
      </td>
      <td className="border-b border-line-soft px-4 py-2.5 font-mono text-xs tabular-nums text-muted">
        {progress}
      </td>
      <td className="border-b border-line-soft px-4 py-2.5">
        {item.rating ? (
          <RatingStars value={Number(item.rating)} size={11} />
        ) : (
          <span className="font-mono text-xs text-faint">—</span>
        )}
      </td>
      <td className="border-b border-line-soft px-4 py-2.5 font-mono text-xs tabular-nums text-muted">
        {new Date(item.created_at).toLocaleDateString(undefined, { day: "2-digit", month: "short" })}
      </td>
    </tr>
  );
}
