/** Bundling in the UI: the Copies panel on an item page, and how a
 * collapsed bundle reads in the table view. */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ItemTable } from "../components/ItemTable";
import ItemDetail from "../pages/ItemDetail";
import type { Item } from "../lib/types";

const PS5_ID = "a507c1f7-56a9-4597-b462-657d69e448cb";
const PC_ID = "b607c1f7-56a9-4597-b462-657d69e448cb";
const BUNDLE = "c707c1f7-56a9-4597-b462-657d69e448cb";

const PS5 = {
  id: PS5_ID,
  user_id: "u",
  type: "game",
  format: "physical",
  status: "completed",
  title: "Elden Ring",
  cover_path: null,
  platform: "PlayStation 5",
  metadata: { developer: "FromSoftware", year: 2022, artwork_fetched: true },
  progress_current: null,
  progress_total: null,
  rating: null,
  review: null,
  purchase_price: null,
  currency: null,
  acquisition_date: null,
  borrowed_by: null,
  loaned_date: null,
  returned_date: null,
  created_at: "2026-03-12T10:00:00Z",
  updated_at: "2026-03-12T10:00:00Z",
  completed_at: null,
  bundle_id: BUNDLE,
  bundle_front: true,
  bundle_count: 2,
  bundle_labels: ["PlayStation 5", "PC (Microsoft Windows)"],
};

const PC = {
  ...PS5,
  id: PC_ID,
  platform: "PC (Microsoft Windows)",
  format: "digital",
  status: "backlog",
  bundle_front: false,
};

const SOLO = {
  ...PS5,
  bundle_id: null,
  bundle_front: false,
  bundle_count: 1,
  bundle_labels: [],
};

/** `copies` is what /copies returns; `search` what the library search returns. */
function mockFetch(item: object, copies: object[], search: object[] = []) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body =
      url.includes("/copies") || url.includes("/bundle")
        ? { copies }
        : url.includes("/activity")
          ? { events: [] }
          : url.includes("/api/items?")
            ? { items: search, total: search.length }
            : item;
    return Promise.resolve({
      ok: true,
      status: method === "DELETE" ? 204 : 200,
      statusText: "OK",
      json: () => Promise.resolve(body),
    } as Response);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof vi.fn>, method: string) {
  return fetchMock.mock.calls
    .filter(([, init]) => ((init as RequestInit | undefined)?.method ?? "GET") === method)
    .map(([url, init]) => ({
      url: String(url),
      body: (init as RequestInit | undefined)?.body
        ? JSON.parse(String((init as RequestInit).body))
        : null,
    }));
}

function renderDetail(id = PS5_ID) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/items/${id}`]}>
        <Routes>
          <Route path="/items/:id" element={<ItemDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function copiesPanel() {
  return (await screen.findByRole("group", { name: /copies/i })) as HTMLElement;
}

afterEach(() => vi.unstubAllGlobals());

describe("Copies panel", () => {
  it("lists every copy in the bundle, the other ones as links", async () => {
    mockFetch(PS5, [PS5, PC]);
    renderDetail();
    const panel = await copiesPanel();

    expect(await within(panel).findByText("PlayStation 5")).toBeInTheDocument();
    const link = within(panel).getByRole("link");
    expect(link).toHaveAttribute("href", `/items/${PC_ID}`);
    expect(link.textContent).toMatch(/PC/);
    expect(link.textContent).toMatch(/Backlog/);
  });

  it("says which copy you are looking at, and which one the library shows", async () => {
    mockFetch(PS5, [PS5, PC]);
    const panel = (renderDetail(), await copiesPanel());

    const current = (await within(panel).findByText(/this copy/i)).closest("div")!;
    expect(current.textContent).toMatch(/PlayStation 5/);
    expect(within(panel).getByText(/in library/i)).toBeInTheDocument();
  });

  it("switches which copy the library shows", async () => {
    const fetchMock = mockFetch(PC, [PS5, PC]);
    renderDetail(PC_ID);
    const panel = await copiesPanel();

    fireEvent.click(await within(panel).findByRole("button", { name: /show in library/i }));
    await waitFor(() =>
      expect(
        calls(fetchMock, "POST").some((c) => c.url.endsWith(`/api/items/${PC_ID}/bundle/front`)),
      ).toBe(true),
    );
  });

  it("unbundles the copy you are looking at", async () => {
    const fetchMock = mockFetch(PC, [PS5, PC]);
    renderDetail(PC_ID);
    const panel = await copiesPanel();

    fireEvent.click(await within(panel).findByRole("button", { name: /unbundle/i }));
    await waitFor(() => {
      const deletes = calls(fetchMock, "DELETE").map((c) => c.url);
      expect(deletes).toHaveLength(1);
      expect(deletes[0].endsWith(`/api/items/${PC_ID}/bundle`)).toBe(true);
    });
  });

  it("bundles another copy found in the library", async () => {
    const fetchMock = mockFetch(SOLO, [], [{ ...PC, bundle_id: null, bundle_count: 1 }]);
    renderDetail();
    const panel = await copiesPanel();
    expect(await within(panel).findByText(/only copy/i)).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole("button", { name: /bundle/i }));
    const search = await screen.findByLabelText(/search your library/i);
    fireEvent.change(search, { target: { value: "elden" } });

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(await within(dialog).findByRole("button", { name: /elden ring/i }));
    await waitFor(() => {
      const post = calls(fetchMock, "POST").find((c) => c.url.endsWith("/bundle"));
      expect(post?.url.endsWith(`/api/items/${PS5_ID}/bundle`)).toBe(true);
      expect(post?.body).toEqual({ item_ids: [PC_ID] });
    });
  });

  it("opens the search on this item's own title — the copy shares it", async () => {
    const fetchMock = mockFetch(SOLO, [], [{ ...PC, bundle_id: null, bundle_count: 1 }]);
    renderDetail();
    fireEvent.click(
      await within(await copiesPanel()).findByRole("button", { name: /bundle another/i }),
    );

    expect(await screen.findByLabelText(/search your library/i)).toHaveValue("Elden Ring");
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("q=Elden+Ring")),
      ).toBe(true),
    );
  });

  it("keeps the item itself and its own copies out of the search results", async () => {
    mockFetch(PS5, [PS5, PC], [PS5, PC, { ...SOLO, id: "d8", title: "Hades" }]);
    renderDetail();
    fireEvent.click(
      await within(await copiesPanel()).findByRole("button", { name: /bundle another/i }),
    );
    fireEvent.change(await screen.findByLabelText(/search your library/i), {
      target: { value: "e" },
    });

    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByText("Hades")).toBeInTheDocument());
    expect(within(dialog).queryByText("Elden Ring")).not.toBeInTheDocument();
  });
});

describe("table view", () => {
  it("marks a row that stands for a bundle", () => {
    render(
      <MemoryRouter>
        <ItemTable items={[{ ...PS5, bundle_count: 3 } as unknown as Item]} />
      </MemoryRouter>,
    );
    expect(screen.getByTitle(/3 copies/i)).toBeInTheDocument();
  });

  it("leaves a single copy unmarked", () => {
    render(
      <MemoryRouter>
        <ItemTable items={[SOLO as unknown as Item]} />
      </MemoryRouter>,
    );
    expect(screen.queryByTitle(/copies/i)).not.toBeInTheDocument();
  });
});
