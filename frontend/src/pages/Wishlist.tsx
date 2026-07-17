/** Wishlist: wanted items with dashed-accent posters and an acquire flow. */

import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AcquireDialog } from "../components/AcquireDialog";
import { EmptyState } from "../components/EmptyState";
import { coverColors } from "../components/PosterCard";
import { PosterGridSkeleton } from "../components/Skeletons";
import { useItems } from "../lib/queries";
import type { Item } from "../lib/types";

export default function Wishlist() {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const { data, isLoading } = useItems({ status: ["wishlist"], q: q || undefined });
  const [acquiring, setAcquiring] = useState<Item | null>(null);

  const items = data?.items ?? [];

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-baseline gap-3.5">
        <h2 className="m-0 text-[26px] font-extrabold tracking-tight">Wishlist</h2>
        <p className="m-0 text-sm text-muted">
          Things you want but don't own yet. Acquiring one moves it to your backlog.
        </p>
      </div>

      {isLoading ? (
        <PosterGridSkeleton count={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No wishes yet"
          message="Add something with status “Wishlist” and it will show up here."
          action={
            <Link to="/add" className="btn btn-sm no-underline">
              Add a wish
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(154px,1fr))] gap-x-4 gap-y-5 max-[760px]:grid-cols-[repeat(auto-fill,minmax(124px,1fr))]">
          {items.map((item) => (
            <WishCard key={item.id} item={item} onAcquire={() => setAcquiring(item)} />
          ))}
        </div>
      )}

      {acquiring && <AcquireDialog item={acquiring} onClose={() => setAcquiring(null)} />}
    </section>
  );
}

function WishCard({ item, onAcquire }: { item: Item; onAcquire: () => void }) {
  const [c1, c2] = coverColors(item.title);
  return (
    <div className="group relative">
      <Link to={`/items/${item.id}`} className="block no-underline text-inherit">
        <div
          className="poster opacity-80 saturate-75"
          style={{
            "--c1": c1,
            "--c2": c2,
            border: "1.5px dashed color-mix(in srgb, var(--accent) 50%, transparent)",
          } as React.CSSProperties}
        >
          {item.cover_path ? (
            <img src={item.cover_path} alt="" loading="lazy" />
          ) : (
            <div className="relative p-3.5 pb-4">
              <div className="font-extrabold leading-tight tracking-tight text-[17px] text-white/95 [text-wrap:balance]">
                {item.title}
              </div>
            </div>
          )}
        </div>
        <div className="px-1 pt-2">
          <div className="truncate text-[13px] font-semibold">{item.title}</div>
          <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-faint">
            <span className="h-[5px] w-[5px] rounded-full" style={{ background: `var(--${item.type})` }} />
            wanted since{" "}
            {new Date(item.created_at).toLocaleDateString(undefined, { month: "short", year: "numeric" })}
          </div>
        </div>
      </Link>
      <button
        type="button"
        onClick={onAcquire}
        className="btn absolute inset-x-2.5 z-10 rounded-[10px] py-2 text-[12.5px] opacity-0 transition-all
          group-hover:opacity-100 group-focus-within:opacity-100 max-[760px]:opacity-100"
        style={{ bottom: 58 }}
      >
        Acquire
      </button>
    </div>
  );
}
