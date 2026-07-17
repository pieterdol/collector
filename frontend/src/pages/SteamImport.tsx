/** Import your Steam library as digital games with playtime prefilled. */

import { useState } from "react";
import { Link } from "react-router-dom";
import { SteamIcon } from "../components/icons";
import { useSteamImport } from "../lib/queries";

export default function SteamImport() {
  const [steamId, setSteamId] = useState("");
  const importer = useSteamImport();

  return (
    <section className="mx-auto max-w-[560px]">
      <div className="mb-1 flex items-center gap-3">
        <SteamIcon size={26} className="text-muted" />
        <h2 className="m-0 text-[26px] font-extrabold tracking-tight">Import from Steam</h2>
      </div>
      <p className="m-0 mb-6 text-[14.5px] text-muted">
        Fetches your owned games and adds them as digital items with playtime prefilled. Already
        imported games are skipped, so you can re-run this any time.
      </p>

      <form
        className="flex gap-2.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (steamId.trim()) importer.mutate(steamId.trim());
        }}
      >
        <input
          value={steamId}
          onChange={(e) => setSteamId(e.target.value)}
          placeholder="SteamID64 or vanity name (e.g. 7656119… or gabelogannewell)"
          className="min-w-0 flex-1 rounded-full border border-line bg-surface px-5 py-2.5 text-sm outline-none focus:border-accent"
        />
        <button type="submit" className="btn" disabled={importer.isPending || !steamId.trim()}>
          {importer.isPending ? "Importing…" : "Import"}
        </button>
      </form>

      <p className="mt-3 text-xs text-faint">
        Your SteamID is in Steam → profile → the number in the URL. Game details must be public
        (Steam privacy settings). Covers appear a few moments after the import.
      </p>

      {importer.isError && (
        <p className="mt-5 rounded-xl bg-surface px-5 py-4 text-sm text-movie">
          {(importer.error as Error).message}
        </p>
      )}

      {importer.data && (
        <div className="mt-5 rounded-xl bg-surface px-5 py-4 text-sm">
          <p className="m-0 font-semibold">
            {importer.data.imported === 0
              ? "Nothing new to import."
              : `Imported ${importer.data.imported} game${importer.data.imported === 1 ? "" : "s"}.`}
          </p>
          <p className="m-0 mt-1 text-muted">
            {importer.data.skipped > 0 && `${importer.data.skipped} already on your shelf · `}
            {importer.data.total} in your Steam library
          </p>
          <Link to="/?type=game" className="btn btn-ghost btn-sm mt-3.5 no-underline">
            View your games
          </Link>
        </div>
      )}
    </section>
  );
}
