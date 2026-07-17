/** Mirrors backend/app/domain/enums.py — keep in sync when adding values. */
export type ItemType = "book" | "movie" | "game";
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
}

export interface ProviderStatus {
  name: string;
  type: ItemType;
  available: boolean;
}

export interface SteamImportResult {
  imported: number;
  skipped: number;
  total: number;
}

export const TYPE_LABEL: Record<ItemType, string> = {
  book: "Book",
  movie: "Movie",
  game: "Game",
};

export const STATUS_LABEL: Record<ItemStatus, string> = {
  wishlist: "Wishlist",
  backlog: "Backlog",
  in_progress: "In progress",
  completed: "Completed",
  abandoned: "Abandoned",
};

/** Unit shown for progress, per medium. Movies don't track progress. */
export function progressUnit(type: ItemType): string | null {
  return type === "book" ? "pages" : type === "game" ? "hours" : null;
}
