/** Import & settings: platform connections (Steam import lives here now)
 * and a note on where metadata comes from. */

import { useState } from "react";
import { Link } from "react-router-dom";
import { SteamIcon } from "../components/icons";
import { useEpicImport, useGogImport, usePsnImport, useSteamImport } from "../lib/queries";
import type { ImportSummary } from "../lib/types";

export default function Settings() {
  return (
    <div className="flex w-full max-w-[640px] flex-col gap-3.5">
      <section className="panel flex flex-col gap-3.5 px-5 py-5">
        <div className="flex flex-col gap-0.5">
          <h2 className="m-0 font-display text-[15px] font-semibold">Connections</h2>
          <p className="m-0 text-[12.5px] text-faint">
            Import your libraries and keep playtime in sync.
          </p>
        </div>
        <SteamConnection />
        <EpicConnection />
        <GogConnection />
        <PsnConnection />
        <p className="m-0 text-xs text-dim">
          Xbox isn't planned — Microsoft's API can't tell owned games apart from Game Pass.
        </p>
      </section>

      <section className="panel flex flex-col gap-2.5 px-5 py-5">
        <h2 className="m-0 font-display text-[15px] font-semibold">Metadata sources</h2>
        <p className="m-0 text-[12.5px] leading-relaxed text-faint">
          Covers and details are enriched from Open Library (books), TMDB (movies &amp; TV) and
          IGDB (games).
        </p>
      </section>
    </div>
  );
}

function SteamConnection() {
  const [steamId, setSteamId] = useState("");
  const importer = useSteamImport();

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line px-4 py-3.5">
      <div className="flex items-center gap-3.5">
        <div
          className="grid h-9 w-9 flex-none place-items-center rounded-[9px] text-accent-ink"
          style={{ background: "var(--game)" }}
        >
          <SteamIcon size={20} />
        </div>
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[13.5px] font-semibold">Steam</span>
          <span className="text-xs text-faint">
            Adds owned games as digital items with playtime prefilled. Already imported games are
            skipped, so you can re-run this any time.
          </span>
        </div>
      </div>

      <form
        className="flex gap-2.5 max-[560px]:flex-col"
        onSubmit={(e) => {
          e.preventDefault();
          if (steamId.trim()) importer.mutate(steamId.trim());
        }}
      >
        <input
          value={steamId}
          onChange={(e) => setSteamId(e.target.value)}
          placeholder="SteamID64 or vanity name (e.g. 7656119… or gabelogannewell)"
          aria-label="Steam ID"
          className="input min-w-0 flex-1"
        />
        <button type="submit" className="btn" disabled={importer.isPending || !steamId.trim()}>
          {importer.isPending ? "Importing…" : "Import"}
        </button>
      </form>

      <p className="m-0 text-xs text-dim">
        Your SteamID is in Steam → profile → the number in the URL. Game details must be public
        (Steam privacy settings). Covers appear a few moments after the import.
      </p>

      <ImportOutcome
        error={importer.isError ? (importer.error as Error) : null}
        data={importer.data}
        totalLabel="in your Steam library"
      />
    </div>
  );
}

function EpicConnection() {
  return (
    <FileImportConnection
      logo="E"
      name="Epic Games"
      description="Owned games from the Epic Games Store — imported from a Heroic or Legendary
        library file, since Epic has no public API. Already imported games are skipped."
      hint={
        <>
          Heroic keeps the file at ~/.config/heroic/store_cache/legendary_library.json (Flatpak:
          ~/.var/app/com.heroicgameslauncher.hgl/config/heroic/…). With Legendary, run{" "}
          <code className="font-mono">legendary list --json &gt; epic.json</code> and upload that.
        </>
      }
      store="Epic"
      importer={useEpicImport()}
    />
  );
}

function GogConnection() {
  return (
    <FileImportConnection
      logo="G"
      name="GOG"
      description="Owned games from GOG — imported from Heroic's library file. Already imported
        games are skipped."
      hint={
        <>
          Heroic keeps the file at ~/.config/heroic/store_cache/gog_library.json (Flatpak:
          ~/.var/app/com.heroicgameslauncher.hgl/config/heroic/…). Sign in to GOG in Heroic once
          so the cache exists.
        </>
      }
      store="GOG"
      importer={useGogImport()}
    />
  );
}

function PsnConnection() {
  const [npsso, setNpsso] = useState("");
  const [includePlus, setIncludePlus] = useState(false);
  const importer = usePsnImport();

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line px-4 py-3.5">
      <div className="flex items-center gap-3.5">
        <div className="grid h-9 w-9 flex-none place-items-center rounded-[9px] border border-line-strong bg-raised font-display text-[15px] font-bold">
          PS
        </div>
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[13.5px] font-semibold">PlayStation Network</span>
          <span className="text-xs text-faint">
            Digitally purchased games with their console (PS5, PS4, …). The token is used once
            and never stored; already imported games are skipped.
          </span>
        </div>
      </div>

      <form
        className="flex gap-2.5 max-[560px]:flex-col"
        onSubmit={(e) => {
          e.preventDefault();
          if (npsso.trim()) {
            importer.mutate({ npsso: npsso.trim(), include_ps_plus: includePlus });
          }
        }}
      >
        <input
          type="password"
          value={npsso}
          onChange={(e) => setNpsso(e.target.value)}
          placeholder="NPSSO token"
          aria-label="NPSSO token"
          autoComplete="off"
          className="input min-w-0 flex-1"
        />
        <button
          type="submit"
          className="btn"
          aria-label="Import PlayStation library"
          disabled={importer.isPending || !npsso.trim()}
        >
          {importer.isPending ? "Importing…" : "Import"}
        </button>
      </form>

      <label className="flex w-fit cursor-pointer items-center gap-2 text-[12.5px] text-muted">
        <input
          type="checkbox"
          checked={includePlus}
          onChange={(e) => setIncludePlus(e.target.checked)}
          aria-label="Include PS Plus games"
        />
        Include PS Plus games (marked, so they stay identifiable if the subscription lapses)
      </label>

      <p className="m-0 text-xs text-dim">
        Sign in at playstation.com, then open ca.account.sony.com/api/v1/ssocookie and copy the
        npsso value. Tokens expire after a couple of months — just grab a new one per import.
      </p>

      <ImportOutcome
        error={importer.isError ? (importer.error as Error) : null}
        data={importer.data}
        totalLabel="in your PSN library"
      />
    </div>
  );
}

/** Upload-a-library-file connection row (Epic, GOG). */
function FileImportConnection({
  logo,
  name,
  store,
  description,
  hint,
  importer,
}: {
  logo: string;
  name: string;
  /** Short store name used in the control labels ("Epic", "GOG"). */
  store: string;
  description: string;
  hint: React.ReactNode;
  importer: ReturnType<typeof useEpicImport>;
}) {
  const [file, setFile] = useState<File | null>(null);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line px-4 py-3.5">
      <div className="flex items-center gap-3.5">
        <div className="grid h-9 w-9 flex-none place-items-center rounded-[9px] border border-line-strong bg-raised font-display text-[15px] font-bold">
          {logo}
        </div>
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[13.5px] font-semibold">{name}</span>
          <span className="text-xs text-faint">{description}</span>
        </div>
      </div>

      <form
        className="flex gap-2.5 max-[560px]:flex-col"
        onSubmit={(e) => {
          e.preventDefault();
          if (file) importer.mutate(file);
        }}
      >
        <input
          type="file"
          accept=".json,application/json"
          aria-label={`${store} library file`}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="input min-w-0 flex-1 cursor-pointer file:mr-3 file:cursor-pointer file:rounded-full
            file:border-0 file:bg-raised file:px-3 file:py-1 file:text-xs file:font-semibold file:text-text"
        />
        <button
          type="submit"
          className="btn"
          aria-label={`Import ${store} library`}
          disabled={importer.isPending || !file}
        >
          {importer.isPending ? "Importing…" : "Import"}
        </button>
      </form>

      <p className="m-0 text-xs text-dim">{hint}</p>

      <ImportOutcome
        error={importer.isError ? (importer.error as Error) : null}
        data={importer.data}
        totalLabel="in the file"
      />
    </div>
  );
}

function ImportOutcome({
  error,
  data,
  totalLabel,
}: {
  error: Error | null;
  data: ImportSummary | undefined;
  totalLabel: string;
}) {
  if (error) {
    return <p className="m-0 rounded-xl bg-surface px-4 py-3 text-sm text-danger">{error.message}</p>;
  }
  if (!data) return null;
  return (
    <div className="rounded-xl bg-surface px-4 py-3 text-sm">
      <p className="m-0 font-semibold">
        {data.imported === 0
          ? "Nothing new to import."
          : `Imported ${data.imported} game${data.imported === 1 ? "" : "s"}.`}
      </p>
      <p className="m-0 mt-1 text-muted">
        {data.skipped > 0 && `${data.skipped} already on your shelf · `}
        {data.total} {totalLabel}
      </p>
      <Link to="/?type=game" className="btn btn-ghost btn-sm mt-3 no-underline">
        View your games
      </Link>
    </div>
  );
}
