/** Wishlist: dashed-accent posters and the acquire flow. */

import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AcquireDialog } from "../components/AcquireDialog";
import { EmptyState } from "../components/EmptyState";
import { coverSrc, describeItem } from "../components/PosterCard";
import { PosterGridSkeleton } from "../components/Skeletons";
import { formatDate } from "../lib/dates";
import { useItems } from "../lib/queries";
import type { Item } from "../lib/types";

export default function Wishlist() {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const { data, isLoading } = useItems({ status: ["wishlist"], q: q || undefined });
  const [acquiring, setAcquiring] = useState<Item | null>(null);

  const items = data?.items ?? [];

  return (
    <>
      <p className="-mt-3 m-0 text-[13.5px] text-muted">
        Things you want but don't own yet. Acquiring one moves it to your backlog.
      </p>

      {isLoading ? (
        <PosterGridSkeleton count={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No wishes yet"
          message="Add something with status “Wishlist” and it will show up here."
          action={
            <Link to="/add" className="btn no-underline">
              + Add a wish
            </Link>
          }
        />
      ) : (
        <section className="grid grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-[18px] max-[820px]:grid-cols-[repeat(auto-fill,minmax(128px,1fr))]">
          {items.map((item) => (
            <WishCard key={item.id} item={item} onAcquire={() => setAcquiring(item)} />
          ))}
        </section>
      )}

      {acquiring && <AcquireDialog item={acquiring} onClose={() => setAcquiring(null)} />}
    </>
  );
}

function WishCard({ item, onAcquire }: { item: Item; onAcquire: () => void }) {
  return (
    <div className="group relative">
      <Link to={`/items/${item.id}`} className="cardlink">
        <div
          className="poster opacity-85 saturate-[0.8]"
          style={{ border: "1.5px dashed color-mix(in oklch, var(--accent) 50%, transparent)" }}
        >
          {item.cover_path ? (
            <img src={coverSrc(item)!} alt="" loading="lazy" />
          ) : (
            <span className="px-3 text-center font-mono text-[10.5px] text-text/45">{item.title}</span>
          )}
        </div>
        <div className="flex flex-col gap-0.5">
          <div className="truncate text-[13.5px] font-semibold leading-[1.3]">{item.title}</div>
          <div className="truncate text-xs text-faint">
            {describeItem(item) || "wanted since"}{" "}
            {formatDate(item.created_at)}
          </div>
        </div>
      </Link>
      <button
        type="button"
        onClick={onAcquire}
        className="btn absolute inset-x-2.5 z-10 py-2 text-[12.5px] opacity-0 transition-opacity
          group-hover:opacity-100 group-focus-within:opacity-100 max-[820px]:hidden"
        style={{ bottom: 56 }}
      >
        Acquire
      </button>
    </div>
  );
}
