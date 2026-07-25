/** TanStack Query hooks — every server interaction goes through here. */

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect } from "react";
import { api, upload } from "./api";
import type {
  ActivityEvent,
  BarcodeResult,
  EnrichSearch,
  Episode,
  EpisodeList,
  ImportSummary,
  Item,
  ItemList,
  ItemType,
  ProviderStatus,
  Season,
  SeasonList,
  Stats,
} from "./types";

export interface ItemFilters {
  type?: string[];
  status?: string[];
  format?: string;
  platform?: string;
  media?: string;
  q?: string;
  sort?: string;
  /** "true" limits to items whose release date hasn't passed. */
  upcoming?: string;
}

export function useItems(filters: ItemFilters) {
  return useQuery({
    queryKey: ["items", filters],
    queryFn: () =>
      api<ItemList>("/api/items", {
        params: { ...filters, limit: 200 },
      }),
  });
}

const PAGE_SIZE = 60;

/** Paged item loading for the library's infinite scroll. */
export function useItemsInfinite(filters: ItemFilters) {
  return useInfiniteQuery({
    queryKey: ["items", "infinite", filters],
    queryFn: ({ pageParam }) =>
      api<ItemList>("/api/items", {
        params: { ...filters, limit: PAGE_SIZE, offset: pageParam },
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((n, page) => n + page.items.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
  });
}

/** Flatten infinite-query pages, dropping items already seen on an earlier
 * page — offset pagination drifts when items are added between page loads. */
export function flattenItemPages(pages: Array<{ items: Item[]; total: number }> | undefined): Item[] {
  const seen = new Set<string>();
  const out: Item[] = [];
  for (const page of pages ?? []) {
    for (const item of page.items) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      out.push(item);
    }
  }
  return out;
}

export function useItem(id: string | undefined) {
  return useQuery({
    queryKey: ["item", id],
    queryFn: () => api<Item>(`/api/items/${id}`),
    enabled: Boolean(id),
  });
}

export function useActivity(id: string | undefined) {
  return useQuery({
    queryKey: ["activity", id],
    queryFn: () => api<{ events: ActivityEvent[] }>(`/api/items/${id}/activity`),
    enabled: Boolean(id),
  });
}

/** Invalidate both the gallery and the single-item cache after a mutation. */
function useInvalidateItems() {
  const client = useQueryClient();
  return (id?: string) => {
    void client.invalidateQueries({ queryKey: ["items"] });
    void client.invalidateQueries({ queryKey: ["stats"] });
    if (id) {
      void client.invalidateQueries({ queryKey: ["item", id] });
      void client.invalidateQueries({ queryKey: ["activity", id] });
    }
  };
}

export function useCreateItem() {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Item>("/api/items", { method: "POST", body }),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateItem(id: string) {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Item>(`/api/items/${id}`, { method: "PATCH", body }),
    onSuccess: () => invalidate(id),
  });
}

export function useDeleteItem() {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/items/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  });
}

export function useAcquireItem(id: string) {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Item>(`/api/items/${id}/acquire`, { method: "POST", body }),
    onSuccess: () => invalidate(id),
  });
}

/** Point an item at a different catalog record; provenance survives
 * server-side, cover and artwork refetch for the new match. */
export function useRelinkItem(id: string) {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (externalId: string) =>
      api<Item>(`/api/items/${id}/relink`, {
        method: "POST",
        body: { external_id: externalId },
      }),
    onSuccess: () => invalidate(id),
  });
}

export function useUploadCover(itemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => upload<Item>(`/api/items/${itemId}/cover`, file),
    onSuccess: (item) => {
      client.setQueryData(["item", itemId], item);
      void client.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useDeleteActivity(itemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (eventId: string) =>
      api<void>(`/api/items/${itemId}/activity/${eventId}`, { method: "DELETE" }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["activity", itemId] });
      void client.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useSeasons(itemId: string | undefined) {
  return useQuery({
    queryKey: ["seasons", itemId],
    queryFn: () => api<SeasonList>(`/api/items/${itemId}/seasons`),
    enabled: Boolean(itemId),
  });
}

export function useUpdateSeason(itemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ seasonNumber, body }: { seasonNumber: number; body: Record<string, unknown> }) =>
      api<Season>(`/api/items/${itemId}/seasons/${seasonNumber}`, { method: "PATCH", body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["seasons", itemId] });
      // Marking a season watched ticks its episodes server-side.
      void client.invalidateQueries({ queryKey: ["episodes", itemId] });
      void client.invalidateQueries({ queryKey: ["activity", itemId] });
      void client.invalidateQueries({ queryKey: ["items"] }); // media filter uses seasons
    },
  });
}

export function useDeleteSeason(itemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (seasonNumber: number) =>
      api<void>(`/api/items/${itemId}/seasons/${seasonNumber}`, { method: "DELETE" }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["seasons", itemId] });
      void client.invalidateQueries({ queryKey: ["activity", itemId] });
      void client.invalidateQueries({ queryKey: ["items"] }); // media filter uses seasons
    },
  });
}

/** Episodes of one season. Rows only exist after a refresh has run, so an
 * empty list is the signal to fetch from TMDB (see SeasonsPanel). */
export function useEpisodes(itemId: string, seasonNumber: number) {
  return useQuery({
    queryKey: ["episodes", itemId, seasonNumber],
    queryFn: () =>
      api<EpisodeList>(`/api/items/${itemId}/seasons/${seasonNumber}/episodes`),
  });
}

export function useRefreshEpisodes(itemId: string, seasonNumber: number) {
  const client = useQueryClient();
  return useMutation({
    // force=true re-asks TMDB inside the cache TTL — for a running show
    // that has aired new episodes.
    mutationFn: (force: boolean) =>
      api<EpisodeList>(`/api/items/${itemId}/seasons/${seasonNumber}/episodes/refresh`, {
        method: "POST",
        params: force ? { force: "true" } : {},
      }),
    onSuccess: (data) => {
      client.setQueryData(["episodes", itemId, seasonNumber], data);
      void client.invalidateQueries({ queryKey: ["seasons", itemId] });
      void client.invalidateQueries({ queryKey: ["activity", itemId] });
    },
  });
}

export function useUpdateEpisode(itemId: string, seasonNumber: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ episodeNumber, watched }: { episodeNumber: number; watched: boolean }) =>
      api<Episode>(
        `/api/items/${itemId}/seasons/${seasonNumber}/episodes/${episodeNumber}`,
        { method: "PATCH", body: { watched } },
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["episodes", itemId, seasonNumber] });
      // The season flag follows its episodes, so the season list moves too.
      void client.invalidateQueries({ queryKey: ["seasons", itemId] });
      void client.invalidateQueries({ queryKey: ["activity", itemId] });
    },
  });
}

export function useEnrichSearch(type: ItemType, q: string) {
  return useQuery({
    queryKey: ["enrich", type, q],
    queryFn: () => api<EnrichSearch>("/api/enrich/search", { params: { type, q } }),
    enabled: q.trim().length >= 2,
    staleTime: 5 * 60 * 1000,
  });
}

export function useEnrichDetails() {
  return useMutation({
    mutationFn: ({ type, externalId }: { type: ItemType; externalId: string }) =>
      api<EnrichSearch>("/api/enrich/details", {
        params: { type, external_id: externalId },
      }),
  });
}

export function useBarcodeLookup() {
  return useMutation({
    mutationFn: (code: string) =>
      api<BarcodeResult>("/api/enrich/barcode", { params: { code } }),
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => api<{ providers: ProviderStatus[] }>("/api/enrich/providers"),
    staleTime: 10 * 60 * 1000,
  });
}

/** Platforms the user actually owns games on (library filter). */
export function usePlatforms() {
  return useQuery({
    queryKey: ["platforms"],
    queryFn: () => api<{ platforms: string[] }>("/api/items/platforms"),
    staleTime: 5 * 60 * 1000,
  });
}

/** The full platform catalog, synced once from IGDB (add-item form). */
export function usePlatformCatalog(enabled: boolean) {
  return useQuery({
    queryKey: ["platform-catalog"],
    queryFn: () =>
      api<{ platforms: Array<{ id: string; name: string; abbreviation: string | null }> }>(
        "/api/platforms",
      ),
    enabled,
    staleTime: 60 * 60 * 1000,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => api<Stats>("/api/stats"),
    staleTime: 30 * 1000,
  });
}

/** Fetch hero/screenshots/description once; server is idempotent. */
export function useFetchArtwork(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<Item>(`/api/items/${id}/artwork`, { method: "POST" }),
    onSuccess: (item) => client.setQueryData(["item", id], item),
  });
}

export function useSteamImport() {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (steamId: string) =>
      api<ImportSummary>("/api/steam/import", {
        method: "POST",
        body: { steam_id: steamId },
      }),
    onSuccess: () => invalidate(),
  });
}

/** Storefront imports run as background jobs the UI polls (big libraries
 * outlive proxy timeouts) and pause in "review" until the user picks
 * which titles to create. Mirrors backend schemas/library_import.py. */
export interface ReviewTitle {
  title_id: string;
  name: string;
  platform: string | null;
  subscription: string | null;
  reason: string | null;
  /** Informational, e.g. the same game owned on another platform. */
  note: string | null;
}

export interface ImportJob {
  status: "running" | "review" | "done" | "error";
  phase: string;
  done: number;
  total: number;
  imported: number | null;
  skipped: number | null;
  detail: string | null;
  candidates: ReviewTitle[] | null;
  excluded: ReviewTitle[] | null;
}

/** Store slugs that back /api/{store}/import. */
export type ImportStore = "psn" | "epic" | "gog";

/** Upload a launcher library file (Epic, GOG) → job id. */
export function useStartFileImport(store: "epic" | "gog") {
  return useMutation({
    mutationFn: (file: File) => upload<{ job_id: string }>(`/api/${store}/import`, file),
  });
}

/** Start a PSN import job: the pasted NPSSO token is exchanged
 * server-side and used once — never stored. */
export function useStartPsnImport() {
  return useMutation({
    mutationFn: (body: { npsso: string; include_ps_plus: boolean; dedupe_cross_gen: boolean }) =>
      api<{ job_id: string }>("/api/psn/import", { method: "POST", body }),
  });
}

/** Confirm an import in review: create items for the selected ids.
 * Invalidating the job query resumes the polling loop. */
export function useConfirmImport(store: ImportStore, jobId: string | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (titleIds: string[]) =>
      api<{ job_id: string }>(`/api/${store}/import/${jobId}/confirm`, {
        method: "POST",
        body: { title_ids: titleIds },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["import-job", store, jobId] }),
  });
}

/** Poll an import job every second while it runs; refresh the library
 * once it completes. */
export function useImportJob(store: ImportStore, jobId: string | null) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["import-job", store, jobId],
    queryFn: () => api<ImportJob>(`/api/${store}/import/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1000 : false),
  });

  const finished = query.data?.status === "done";
  useEffect(() => {
    if (!finished) return;
    void client.invalidateQueries({ queryKey: ["items"] });
    void client.invalidateQueries({ queryKey: ["stats"] });
  }, [finished]); // eslint-disable-line react-hooks/exhaustive-deps

  return query;
}
