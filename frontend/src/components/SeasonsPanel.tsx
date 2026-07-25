/** Per-season and per-episode tracking for TV shows.
 *
 * Seasons are a compact accordion: a thumbnail-sized poster, the name, air
 * year, episode count and watch progress in one row. Opening a row reveals
 * that season's options (ownership, format, disc media, the whole-season
 * watched control) and its episode checklist. Episodes come from TMDB the
 * first time a season is opened — never at add time — so a show nobody
 * expands costs no API calls. Rows come from TMDB at add time; manual shows
 * grow rows via "Add season" (the PATCH endpoint upserts), and manually
 * added rows (no TMDB season id) can be removed again. The show-level
 * format/media in Details stays the whole-show fallback.
 */

import { useEffect, useRef, useState } from "react";
import { formatDate } from "../lib/dates";
import {
  useDeleteSeason,
  useEpisodes,
  useRefreshEpisodes,
  useSeasons,
  useUpdateEpisode,
  useUpdateSeason,
} from "../lib/queries";
import type { Episode, Season } from "../lib/types";
import { MOVIE_MEDIA } from "../lib/types";
import { ChevronIcon } from "./icons";
import { DiscBadge } from "./MediaBadge";

export function SeasonsPanel({ itemId }: { itemId: string }) {
  const { data } = useSeasons(itemId);
  const update = useUpdateSeason(itemId);
  const del = useDeleteSeason(itemId);
  const [open, setOpen] = useState<number[]>([]);
  // Seasons that already asked TMDB for episodes. Lives here so collapsing
  // and reopening a row doesn't fire the lookup again.
  const asked = useRef(new Set<number>());
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
        <div className="flex flex-col gap-1.5">
          {seasons.map((season) => (
            <SeasonRow
              key={season.id}
              itemId={itemId}
              season={season}
              busy={busy}
              open={open.includes(season.season_number)}
              asked={asked.current}
              onToggle={() =>
                setOpen((current) =>
                  current.includes(season.season_number)
                    ? current.filter((n) => n !== season.season_number)
                    : [...current, season.season_number],
                )
              }
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

function SeasonRow({
  itemId,
  season,
  busy,
  open,
  asked,
  onToggle,
  onChange,
  onRemove,
}: {
  itemId: string;
  season: Season;
  busy: boolean;
  open: boolean;
  asked: Set<number>;
  onToggle: () => void;
  onChange: (body: Record<string, unknown>) => void;
  onRemove: () => void;
}) {
  const name = season.name ?? `Season ${season.season_number}`;
  const facts = [
    season.air_date ? season.air_date.slice(0, 4) : null,
    season.episode_count !== null ? `${season.episode_count} eps` : null,
    season.ownership,
  ].filter(Boolean) as string[];

  return (
    <div className="overflow-hidden rounded-[11px] border border-line">
      <button
        type="button"
        aria-label={`${name} details`}
        aria-expanded={open}
        onClick={onToggle}
        className={`flex w-full items-center gap-3 px-2.5 py-2 text-left hover:bg-raised ${
          open ? "bg-raised" : ""
        }`}
      >
        <span className="poster h-[51px] w-[34px] flex-none rounded-md">
          {season.poster_path ? (
            <img src={season.poster_path} alt="" loading="lazy" />
          ) : (
            <span className="font-mono text-[10px] text-text/45">S{season.season_number}</span>
          )}
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate text-[13px] font-semibold text-text">{name}</span>
          <span className="flex min-w-0 items-center gap-1.5 truncate font-mono text-[10.5px] text-dim">
            {facts.map((fact, index) => (
              <span key={fact} className="flex items-center gap-1.5">
                {index > 0 && <span className="text-faint">·</span>}
                {fact}
              </span>
            ))}
          </span>
        </span>
        {season.format === "physical" && season.media && (
          <DiscBadge
            media={season.media}
            to={`/?type=tv&media=${encodeURIComponent(season.media)}`}
            inline
          />
        )}
        <WatchState season={season} />
        <ChevronIcon
          className={`flex-none text-faint transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open && (
        <div className="flex flex-col gap-3 border-t border-line px-3 py-3">
          <SeasonOptions season={season} name={name} busy={busy} onChange={onChange} />
          <EpisodeList itemId={itemId} season={season} asked={asked} />
          {season.tmdb_season_id === null && (
            <RemoveSeason name={name} busy={busy} onRemove={onRemove} />
          )}
        </div>
      )}
    </div>
  );
}

/** Progress on the collapsed row: episode counts once they're tracked,
 * otherwise the plain season flag. */
function WatchState({ season }: { season: Season }) {
  if (season.episodes_tracked > 0) {
    const done = season.episodes_watched === season.episodes_tracked;
    return (
      <span
        className="flex-none whitespace-nowrap font-mono text-[11px]"
        style={{ color: done ? "var(--done)" : "var(--muted)" }}
      >
        {season.episodes_watched} / {season.episodes_tracked}
      </span>
    );
  }
  if (season.watched) {
    return (
      <span
        className="pillbadge flex-none whitespace-nowrap text-[10.5px]"
        style={{
          color: "var(--done)",
          background: "color-mix(in oklch, var(--done) 14%, transparent)",
        }}
      >
        Watched
      </span>
    );
  }
  return null;
}

function SeasonOptions({
  season,
  name,
  busy,
  onChange,
}: {
  season: Season;
  name: string;
  busy: boolean;
  onChange: (body: Record<string, unknown>) => void;
}) {
  return (
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
      {/* Bulk control: the server ticks every episode of the season with it. */}
      <label className="ml-auto flex cursor-pointer items-center gap-1.5 text-[11.5px] text-muted">
        <input
          type="checkbox"
          aria-label={season.watched ? `Mark ${name} unwatched` : `Mark ${name} watched`}
          checked={season.watched}
          disabled={busy}
          onChange={(e) => onChange({ watched: e.target.checked })}
          className="h-3.5 w-3.5 cursor-pointer"
          style={{ accentColor: "var(--done)" }}
        />
        Whole season
      </label>
    </div>
  );
}

/** The season's episodes, fetched from TMDB the first time it is opened. */
function EpisodeList({
  itemId,
  season,
  asked,
}: {
  itemId: string;
  season: Season;
  asked: Set<number>;
}) {
  const number = season.season_number;
  const { data, isLoading } = useEpisodes(itemId, number);
  const refresh = useRefreshEpisodes(itemId, number);
  const update = useUpdateEpisode(itemId, number);
  const linked = season.tmdb_season_id !== null;

  useEffect(() => {
    if (!linked || !data || data.total > 0 || asked.has(number)) return;
    asked.add(number);
    refresh.mutate(false);
  }, [data, linked, number]); // eslint-disable-line react-hooks/exhaustive-deps

  const episodes = data?.episodes ?? [];
  const loading = isLoading || refresh.isPending;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
          Episodes
        </span>
        <span className="flex items-baseline gap-2.5">
          {data && data.total > 0 && (
            <span className="font-mono text-[11px] text-dim">
              {data.watched} of {data.total} watched
            </span>
          )}
          {linked && (
            <button
              type="button"
              aria-label="Check TMDB for new episodes"
              className="text-[11.5px] font-semibold text-accent disabled:opacity-50"
              disabled={loading}
              onClick={() => refresh.mutate(true)}
            >
              Refresh
            </button>
          )}
        </span>
      </div>

      {episodes.map((episode) => (
        <EpisodeRow
          key={episode.id}
          episode={episode}
          seasonNumber={number}
          busy={update.isPending}
          onToggle={(watched) => update.mutate({ episodeNumber: episode.episode_number, watched })}
        />
      ))}

      {episodes.length === 0 && (
        <p className="m-0 text-[12px] text-faint">
          {loading
            ? "Loading episodes…"
            : linked
              ? "TMDB has no episode list for this season."
              : "No episode list — episodes come from TMDB, and this season was added by hand."}
        </p>
      )}
      {refresh.isError && (
        <p className="m-0 text-[11.5px] text-danger">{(refresh.error as Error).message}</p>
      )}
    </div>
  );
}

function EpisodeRow({
  episode,
  seasonNumber,
  busy,
  onToggle,
}: {
  episode: Episode;
  seasonNumber: number;
  busy: boolean;
  onToggle: (watched: boolean) => void;
}) {
  const code = `S${seasonNumber}E${episode.episode_number}`;
  return (
    <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1.5 py-1 hover:bg-raised">
      <input
        type="checkbox"
        aria-label={episode.watched ? `Mark ${code} unwatched` : `Mark ${code} watched`}
        checked={episode.watched}
        disabled={busy}
        onChange={(e) => onToggle(e.target.checked)}
        className="h-3.5 w-3.5 flex-none cursor-pointer"
        style={{ accentColor: "var(--done)" }}
      />
      <span className="w-5 flex-none font-mono text-[11px] text-dim">
        {episode.episode_number}
      </span>
      <span
        className={`min-w-0 flex-1 truncate text-[12.5px] ${
          episode.watched ? "text-muted" : "text-body"
        }`}
      >
        {episode.name ?? code}
      </span>
      {episode.runtime !== null && (
        <span className="flex-none font-mono text-[10.5px] text-faint">{episode.runtime}m</span>
      )}
      {episode.air_date && (
        <span className="flex-none whitespace-nowrap font-mono text-[10.5px] text-dim">
          {formatDate(episode.air_date)}
        </span>
      )}
    </label>
  );
}

function RemoveSeason({
  name,
  busy,
  onRemove,
}: {
  name: string;
  busy: boolean;
  onRemove: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
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
    );
  }
  return (
    <button
      type="button"
      aria-label={`Remove ${name}`}
      onClick={() => setConfirming(true)}
      className="w-fit text-[11.5px] font-semibold text-danger"
    >
      Remove
    </button>
  );
}
