/** Per-season ownership and watch tracking for TV shows.
 *
 * Seasons render as poster cards (same look as the library grid), with
 * the disc-media badge on the art. Rows come from TMDB at add time;
 * manual shows grow rows via "Add season" (the PATCH endpoint upserts),
 * and manually added rows (no TMDB season id) can be removed again. The
 * show-level format/media in Details stays the whole-show fallback.
 */

import { useState } from "react";
import { useDeleteSeason, useSeasons, useUpdateSeason } from "../lib/queries";
import type { Season } from "../lib/types";
import { MOVIE_MEDIA } from "../lib/types";
import { DiscBadge } from "./MediaBadge";

export function SeasonsPanel({ itemId }: { itemId: string }) {
  const { data } = useSeasons(itemId);
  const update = useUpdateSeason(itemId);
  const del = useDeleteSeason(itemId);
  if (!data) return null;

  const seasons = data.seasons ?? [];
  const nextNumber = seasons.reduce((max, s) => Math.max(max, s.season_number), 0) + 1;
  const busy = update.isPending || del.isPending;

  return (
    <div className="panel flex flex-col gap-3 p-5">
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
      {seasons.length > 0 && (
        <div className="grid grid-cols-3 gap-3.5 max-[1240px]:grid-cols-2 max-[420px]:grid-cols-1">
          {seasons.map((season) => (
            <SeasonCard
              key={season.id}
              season={season}
              busy={busy}
              onChange={(body) => update.mutate({ seasonNumber: season.season_number, body })}
              onRemove={() => del.mutate(season.season_number)}
            />
          ))}
        </div>
      )}
      <button
        type="button"
        className="w-fit text-[12.5px] font-semibold text-accent"
        disabled={busy}
        onClick={() => update.mutate({ seasonNumber: nextNumber, body: {} })}
      >
        Add season
      </button>
    </div>
  );
}

function SeasonCard({
  season,
  busy,
  onChange,
  onRemove,
}: {
  season: Season;
  busy: boolean;
  onChange: (body: Record<string, unknown>) => void;
  onRemove: () => void;
}) {
  const name = season.name ?? `Season ${season.season_number}`;
  const manual = season.tmdb_season_id === null;
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="poster" style={{ "--mc": "var(--tv)" } as React.CSSProperties}>
        {season.poster_path ? (
          <img src={season.poster_path} alt="" loading="lazy" />
        ) : (
          <span className="px-2 text-center font-mono text-[10.5px] text-text/45">{name}</span>
        )}
        {season.watched && (
          <span className="badge" style={{ color: "var(--done)" }}>
            Watched
          </span>
        )}
        {season.format === "physical" && season.media && (
          <DiscBadge
            media={season.media}
            to={`/?type=tv&media=${encodeURIComponent(season.media)}`}
          />
        )}
      </div>
      <div className="flex items-baseline justify-between gap-2">
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
          disabled={busy}
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
            disabled={busy}
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
            disabled={busy}
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
        <label className="flex cursor-pointer items-center gap-1.5 text-[11.5px] text-muted">
          <input
            type="checkbox"
            aria-label={season.watched ? `Mark ${name} unwatched` : `Mark ${name} watched`}
            checked={season.watched}
            disabled={busy}
            onChange={(e) => onChange({ watched: e.target.checked })}
            className="h-3.5 w-3.5 cursor-pointer"
            style={{ accentColor: "var(--done)" }}
          />
          Watched
        </label>
      </div>
      {manual &&
        (confirming ? (
          <span className="flex items-center gap-2.5 text-xs text-muted">
            Remove {name}?
            <button
              type="button"
              className="font-semibold text-danger"
              disabled={busy}
              onClick={() => {
                setConfirming(false);
                onRemove();
              }}
            >
              Delete
            </button>
            <button type="button" className="text-muted" onClick={() => setConfirming(false)}>
              Keep
            </button>
          </span>
        ) : (
          <button
            type="button"
            aria-label={`Remove ${name}`}
            onClick={() => setConfirming(true)}
            className="w-fit text-[11.5px] font-semibold text-danger"
          >
            Remove
          </button>
        ))}
    </div>
  );
}
