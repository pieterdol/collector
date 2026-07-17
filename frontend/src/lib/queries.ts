/** TanStack Query hooks — every server interaction goes through here. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  ActivityEvent,
  BarcodeResult,
  EnrichSearch,
  Item,
  ItemList,
  ItemType,
  ProviderStatus,
  SteamImportResult,
} from "./types";

export interface ItemFilters {
  type?: string[];
  status?: string[];
  format?: string;
  q?: string;
  sort?: string;
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

export function useSteamImport() {
  const invalidate = useInvalidateItems();
  return useMutation({
    mutationFn: (steamId: string) =>
      api<SteamImportResult>("/api/steam/import", {
        method: "POST",
        body: { steam_id: steamId },
      }),
    onSuccess: () => invalidate(),
  });
}
