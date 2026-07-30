/** Mirrors backend/app/domain/enums.py — keep in sync when adding values. */
export type ItemType = "book" | "movie" | "tv" | "game" | "music";
export type ItemFormat = "physical" | "digital";
export type ItemStatus = "wishlist" | "backlog" | "in_progress" | "completed" | "abandoned";

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface Item {
  id: string;
  user_id: string;
  type: ItemType;
  format: ItemFormat | null;
  status: ItemStatus;
  title: string;
  cover_path: string | null;
  metadata: Record<string, unknown>;
  /** Resolved platform name (games), from the linked platform record. */
  platform: string | null;
  progress_current: string | null;
  progress_total: string | null;
  rating: string | null;
  review: string | null;
  purchase_price: string | null;
  currency: string | null;
  acquisition_date: string | null;
  borrowed_by: string | null;
  loaned_date: string | null;
  returned_date: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ItemList {
  items: Item[];
  total: number;
}

export type SeasonOwnership = "owned" | "wishlist";

/** One tracked TV season — mirrors backend SeasonOut. */
export interface Season {
  id: string;
  item_id: string;
  season_number: number;
  tmdb_season_id: number | null;
  name: string | null;
  episode_count: number | null;
  air_date: string | null;
  poster_path: string | null;
  ownership: SeasonOwnership | null;
  format: ItemFormat | null;
  media: string | null;
  watched: boolean;
  /** 0 until the season's episodes have been fetched (on first open). */
  episodes_tracked: number;
  episodes_watched: number;
  created_at: string;
  updated_at: string;
}

export interface SeasonList {
  seasons: Season[];
  /** Aggregates skip Specials (season 0). */
  total_seasons: number;
  owned_seasons: number;
  watched_seasons: number;
}

/** One tracked episode of a season — mirrors backend EpisodeOut. */
export interface Episode {
  id: string;
  season_id: string;
  episode_number: number;
  tmdb_episode_id: number | null;
  name: string | null;
  overview: string | null;
  air_date: string | null;
  runtime: number | null;
  watched: boolean;
  created_at: string;
  updated_at: string;
}

export interface EpisodeList {
  episodes: Episode[];
  total: number;
  watched: number;
}

export interface ActivityEvent {
  id: string;
  event_type: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  created_at: string;
}

export interface EnrichResult {
  title: string;
  type: ItemType;
  metadata: Record<string, unknown>;
  cover_url: string | null;
  external_id: string | null;
}

export interface EnrichSearch {
  provider: string;
  available: boolean;
  results: EnrichResult[];
}

export interface BarcodeResult {
  code: string;
  kind: "isbn" | "upc";
  matched: boolean;
  result: EnrichResult | null;
  /** The user's item carrying this code, when they already added it. Set
   * means the catalog was skipped, so `matched`/`result` say nothing. */
  owned_item_id: string | null;
}

export interface ProviderStatus {
  name: string;
  type: ItemType;
  available: boolean;
}

/** Shared shape of the bulk importers (Steam, Epic). */
export interface ImportSummary {
  imported: number;
  skipped: number;
  total: number;
}

export interface Stats {
  tiles: {
    book: { total: number; in_progress: number; completed_this_year: number };
    tv: { total: number; physical: number; digital: number };
    movie: { total: number; physical: number; digital: number };
    game: { total: number; via_steam: number; hours_played: number };
    music: { total: number; vinyl: number; cd: number };
    value: { total: string; this_month: string; currency: string };
  };
  continue: Array<{
    id: string;
    title: string;
    type: ItemType;
    sub: string;
    progress_current: number | null;
    progress_total: number | null;
    pct: number | null;
  }>;
  loans: Array<{ id: string; title: string; borrowed_by: string; loaned_date: string | null }>;
  recent: Array<{
    item_id: string;
    title: string;
    type: ItemType;
    event_type: string;
    old_value: Record<string, unknown> | null;
    new_value: Record<string, unknown> | null;
    created_at: string;
  }>;
}

export const TYPE_LABEL: Record<ItemType, string> = {
  book: "Book",
  tv: "TV",
  movie: "Movie",
  game: "Game",
  music: "Music",
};

export const STATUS_LABEL: Record<ItemStatus, string> = {
  wishlist: "Wishlist",
  backlog: "Backlog",
  in_progress: "In progress",
  completed: "Completed",
  abandoned: "Abandoned",
};

/** Disc formats a physical movie or TV season can be stored on
 * (metadata.media / item_seasons.media — mirrors DiscMedia in enums.py). */
export const MOVIE_MEDIA = ["DVD", "Blu-ray", "Ultra HD Blu-ray", "VHS"];

/** Carriers a physical record can be stored on (metadata.media — mirrors
 * MusicMedia in enums.py). Vinyl sizes stay separate: that's the
 * distinction a collector files by. */
export const MUSIC_MEDIA = [
  "Vinyl LP",
  'Vinyl 12"',
  'Vinyl 10"',
  'Vinyl 7"',
  "CD",
  "Cassette",
];

/** The media options for a type — records and discs don't mix. */
export function mediaOptions(type: string): string[] {
  return type === "music" ? MUSIC_MEDIA : type === "movie" || type === "tv" ? MOVIE_MEDIA : [];
}

/** Unit shown for progress, per medium. Movies don't track progress. */
export function progressUnit(type: ItemType): string | null {
  return type === "book" ? "pages" : type === "game" ? "hours" : null;
}
