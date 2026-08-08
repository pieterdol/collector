/** Header search box, bound to the ?q= URL param (library + wishlist).
 *
 * The API searches titles, creators (authors/artists/directors/studios) and
 * synopses, ranked in that order — see list_items in backend/app/api/items.py. */

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { SearchIcon, XIcon } from "./icons";

const DEBOUNCE_MS = 250;

export function SearchBox() {
  const [params, setParams] = useSearchParams();
  const [value, setValue] = useState(params.get("q") ?? "");
  const inputRef = useRef<HTMLInputElement>(null);
  // The last term we put in the URL ourselves. Our own write comes back as a
  // params change one flush later, and adopting that echo overwrote whatever
  // had been typed in between — a keystroke landing next to the debounce was
  // simply lost ("Far Cry" arriving as "Fr Cry").
  const ownWrite = useRef(params.get("q") ?? "");

  // Follow the URL when something else changes it — back/forward, a filter
  // link — but never when it is only our own search coming back.
  useEffect(() => {
    const term = params.get("q") ?? "";
    if (term === ownWrite.current) return;
    ownWrite.current = term;
    setValue(term);
  }, [params]);

  // Typing is debounced; every other filter in the URL is left alone.
  function commit(term: string) {
    ownWrite.current = term;
    const next = new URLSearchParams(params);
    if (term) next.set("q", term);
    else next.delete("q");
    setParams(next, { replace: true });
  }

  useEffect(() => {
    const handle = setTimeout(() => {
      if (value !== (params.get("q") ?? "")) commit(value);
    }, DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  function clear() {
    setValue("");
    commit(""); // an explicit action — no reason to make it wait
    inputRef.current?.focus();
  }

  return (
    <div className="relative min-w-[220px] flex-1 max-w-[420px] max-[820px]:order-last max-[820px]:max-w-none max-[820px]:basis-full">
      <SearchIcon size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 opacity-50" />
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && value && clear()}
        placeholder="Search titles, authors, artists…"
        // input-clearable hides the browser's own search cancel button, so
        // WebKit doesn't show a second × next to ours.
        className="input input-clearable w-full"
        style={{ paddingLeft: 36, paddingRight: value ? 34 : undefined }}
      />
      {value && (
        <button
          type="button"
          aria-label="Clear search"
          title="Clear search (Esc)"
          onClick={clear}
          className="absolute right-1.5 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-faint transition-colors hover:bg-raised hover:text-text"
        >
          <XIcon size={12} />
        </button>
      )}
    </div>
  );
}
