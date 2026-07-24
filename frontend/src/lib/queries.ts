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

/** Epic import: upload a Heroic store cache or `legendary list --json` file. */
export function useEpicImport() {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (file: File) => upload<ImportSummary>("/api/epic/import", file),
    onSuccess: () => invalidate(),
  });
}

/** A PSN import runs as a background job the UI polls (big libraries
 * outlive proxy timeouts). Mirrors backend schemas/psn.py. */
export interface PsnImportJob {
  status: "running" | "done" | "error";
  phase: string;
  done: number;
  total: number;
  imported: number | null;
  skipped: number | null;
  detail: string | null;
}

/** Start a PSN import job: the pasted NPSSO token is exchanged
 * server-side and used once — never stored. */
export function useStartPsnImport() {
  return useMutation({
    mutationFn: (body: { npsso: string; include_ps_plus: boolean; dedupe_cross_gen: boolean }) =>
      api<{ job_id: string }>("/api/psn/import", { method: "POST", body }),
  });
}

/** Poll a PSN import job every second while it runs; refresh the
 * library once it completes. */
export function usePsnImportJob(jobId: string | null) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["psn-import", jobId],
    queryFn: () => api<PsnImportJob>(`/api/psn/import/${jobId}`),
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

/** GOG import: upload Heroic's gog_library.json store cache. */
export function useGogImport() {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (file: File) => upload<ImportSummary>("/api/gog/import", file),
    onSuccess: () => invalidate(),
  });
}
