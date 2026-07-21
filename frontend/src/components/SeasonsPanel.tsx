/** Per-season ownership and watch tracking for TV shows.
 *
 * Rows are created from TMDB at add time; manual shows grow rows via
 * "Add season" (the PATCH endpoint upserts). The show-level format/media
 * in Details stays the whole-show fallback (complete-series box sets).
 */

import { useSeasons, useUpdateSeason } from "../lib/queries";
import type { Season } from "../lib/types";
import { MOVIE_MEDIA } from "../lib/types";

export function SeasonsPanel({ itemId }: { itemId: string }) {
  const { data } = useSeasons(itemId);
  const update = useUpdateSeason(itemId);
  if (!data) return null;

  const seasons = data.seasons ?? [];
  const nextNumber = seasons.reduce((max, s) => Math.max(max, s.season_number), 0) + 1;

  return (
    <div className="panel flex flex-col gap-2.5 p-5">
      <div className="flex items-baseline justify-between">
        <div className="paneltitle">Seasons</div>
        {data.total_seasons > 0 && (
          <span className="font-mono text-[11.5px] text-dim">
            {data.watched_seasons} of {data.total_seasons} watched
          </span>
        )}
      </div>
      {seasons.length === 0 && (
        <p className="m-0 text-[12.5px] text-faint">No seasons tracked yet.</p>
      )}
      {seasons.map((season) => (
        <SeasonRow
          key={season.id}
          season={season}
          disabled={update.isPending}
          onChange={(body) => update.mutate({ seasonNumber: season.season_number, body })}
        />
      ))}
      <button
        type="button"
        className="w-fit text-[12.5px] font-semibold text-accent"
        disabled={update.isPending}
        onClick={() => update.mutate({ seasonNumber: nextNumber, body: {} })}
      >
        Add season
      </button>
    </div>
  );
}

function SeasonRow({
  season,
  disabled,
  onChange,
}: {
  season: Season;
  disabled: boolean;
  onChange: (body: Record<string, unknown>) => void;
}) {
  const name = season.name ?? `Season ${season.season_number}`;
  return (
    <div className="flex items-center gap-3 border-b border-line/60 pb-2.5 last:border-b-0 last:pb-0">
      {season.poster_path ? (
        <img
          src={season.poster_path}
          alt=""
          loading="lazy"
          className="h-14 w-10 flex-none rounded-md border border-line object-cover"
          style={{ background: "var(--shot-bg)" }}
        />
      ) : (
        <div
          className="h-14 w-10 flex-none rounded-md border border-line"
          style={{ background: "var(--shot-bg)" }}
        />
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-baseline gap-2">
          <span className="truncate text-[13px] font-semibold text-text">{name}</span>
          {season.episode_count !== null && (
            <span className="whitespace-nowrap font-mono text-[11px] text-dim">
              {season.episode_count} eps
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <select
            aria-label={`${name} ownership`}
            value={season.ownership ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ ownership: e.target.value || null })}
            className="input w-auto cursor-pointer px-1.5 py-0.5 text-[11.5px]"
          >
            <option value="">Not tracked</option>
            <option value="owned">Owned</option>
            <option value="wishlist">Wishlist</option>
          </select>
          {season.ownership === "owned" && (
            <select
              aria-label={`${name} format`}
              value={season.format ?? ""}
              disabled={disabled}
              onChange={(e) => onChange({ format: e.target.value || null })}
              className="input w-auto cursor-pointer px-1.5 py-0.5 text-[11.5px]"
            >
              <option value="">Format…</option>
              <option value="physical">physical</option>
              <option value="digital">digital</option>
            </select>
          )}
          {season.ownership === "owned" && season.format === "physical" && (
            <select
              aria-label={`${name} media`}
              value={season.media ?? ""}
              disabled={disabled}
              onChange={(e) => onChange({ media: e.target.value || null })}
              className="input w-auto cursor-pointer px-1.5 py-0.5 text-[11.5px]"
            >
              <option value="">Media…</option>
              {MOVIE_MEDIA.map((media) => (
                <option key={media} value={media}>
                  {media}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
      <input
        type="checkbox"
        aria-label={season.watched ? `Mark ${name} unwatched` : `Mark ${name} watched`}
        title={season.watched ? "Watched" : "Mark watched"}
        checked={season.watched}
        disabled={disabled}
        onChange={(e) => onChange({ watched: e.target.checked })}
        className="h-4 w-4 flex-none cursor-pointer"
        style={{ accentColor: "var(--done)" }}
      />
    </div>
  );
}
