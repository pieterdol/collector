/** Scan flow: a code already in the collection opens that item instead of
 * starting a duplicate. Driven through the type-the-digits fallback — jsdom
 * has no camera. */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useParams } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import AddItem from "../pages/AddItem";

const ITEM_ID = "a507c1f7-56a9-4597-b462-657d69e448cb";

const PROVIDERS = {
  providers: [
    { name: "openlibrary", type: "book", available: true },
    { name: "tmdb", type: "movie", available: true },
    { name: "tmdb", type: "tv", available: true },
    { name: "igdb", type: "game", available: true },
    { name: "musicbrainz", type: "music", available: true },
  ],
};

function mockFetch(barcode: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/enrich/barcode")
        ? barcode
        : url.includes("/api/enrich/providers")
          ? PROVIDERS
          : { provider: "openlibrary", available: true, results: [] };
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve(body),
      } as Response);
    }),
  );
}

/** Stands in for the item page, reporting what it was routed with. */
function ItemPageStub() {
  const { id } = useParams();
  const state = useLocation().state as { scanned?: string } | null;
  return <div>{`item ${id} scanned ${state?.scanned ?? "-"}`}</div>;
}

function renderScan() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/add?mode=scan"]}>
        <Routes>
          <Route path="/add" element={<AddItem />} />
          <Route path="/items/:id" element={<ItemPageStub />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function lookUp(code: string) {
  const input = await screen.findByPlaceholderText("…or type the barcode digits");
  fireEvent.change(input, { target: { value: code } });
  fireEvent.click(screen.getByRole("button", { name: "Look up" }));
}

describe("AddItem scan", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("opens the item you already have instead of adding it twice", async () => {
    mockFetch({
      code: "9780441172719",
      kind: "isbn",
      matched: false,
      result: null,
      owned_item_id: ITEM_ID,
    });
    renderScan();

    await lookUp("9780441172719");

    expect(
      await screen.findByText(`item ${ITEM_ID} scanned 9780441172719`),
    ).toBeInTheDocument();
  });

  it("still prefills the confirm form for a code that is new to you", async () => {
    mockFetch({
      code: "9780441172719",
      kind: "isbn",
      matched: true,
      owned_item_id: null,
      result: {
        title: "Dune",
        type: "book",
        metadata: { authors: ["Frank Herbert"], isbn: "9780441172719" },
        cover_url: null,
        external_id: "9780441172719",
      },
    });
    renderScan();

    await lookUp("9780441172719");

    expect(await screen.findByDisplayValue("Dune")).toBeInTheDocument();
    expect(screen.queryByText(/^item /)).not.toBeInTheDocument();
  });

  it("reports an ISBN no catalog knows without leaving the scanner", async () => {
    mockFetch({
      code: "9780000000002",
      kind: "isbn",
      matched: false,
      result: null,
      owned_item_id: null,
    });
    renderScan();

    await lookUp("9780000000002");

    await waitFor(() =>
      expect(screen.getByText(/No book found for ISBN 9780000000002/)).toBeInTheDocument(),
    );
  });
});
