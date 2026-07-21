import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ItemDetail from "../pages/ItemDetail";

const ID = "a507c1f7-56a9-4597-b462-657d69e448cb";

const GAME = {
  id: ID,
  user_id: "u",
  type: "game",
  format: "physical",
  status: "completed",
  title: "Sekiro: Shadows Die Twice",
  cover_path: null,
  platform: "PlayStation 4",
  metadata: { developer: "FromSoftware", year: 2019, artwork_fetched: true },
  progress_current: null,
  progress_total: null,
  rating: "5.0",
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
};

function mockFetch(item: object = GAME) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/activity") ? { events: [] } : item;
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve(body),
      } as Response);
    }),
  );
}

function renderDetail() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/items/${ID}`]}>
        <Routes>
          <Route path="/items/:id" element={<ItemDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ItemDetail details panel", () => {
  beforeEach(() => mockFetch());
  afterEach(() => vi.unstubAllGlobals());

  it("links the platform to the filtered library", async () => {
    renderDetail();

    const link = await screen.findByRole("link", { name: "PlayStation 4" });
    expect(link).toHaveAttribute("href", "/?type=game&platform=PlayStation%204");
  });

  it("labels the TV creator as Creator, not Director", async () => {
    vi.unstubAllGlobals();
    mockFetch({
      ...GAME,
      type: "tv",
      platform: null,
      metadata: { director: "Vince Gilligan", year: 2008, artwork_fetched: true },
    });
    renderDetail();

    expect(await screen.findByText("Creator")).toBeInTheDocument();
    expect(screen.getByText("Vince Gilligan")).toBeInTheDocument();
    expect(screen.queryByText("Director")).not.toBeInTheDocument();
  });

  it("shows seasons and episodes for a TV show", async () => {
    vi.unstubAllGlobals();
    mockFetch({
      ...GAME,
      type: "tv",
      platform: null,
      metadata: {
        number_of_seasons: 8,
        number_of_episodes: 73,
        artwork_fetched: true,
      },
    });
    renderDetail();

    expect(await screen.findByText("Seasons")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("Episodes")).toBeInTheDocument();
    expect(screen.getByText("73")).toBeInTheDocument();
  });

  it("describes season activity events", async () => {
    vi.unstubAllGlobals();
    const item = {
      ...GAME,
      type: "tv",
      platform: null,
      metadata: { artwork_fetched: true },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("/activity")
          ? {
              events: [
                {
                  id: "e1",
                  event_type: "season_watched",
                  old_value: { season_number: 3, watched: false },
                  new_value: { season_number: 3, watched: true },
                  created_at: "2026-07-21T10:00:00Z",
                },
                {
                  id: "e2",
                  event_type: "season_acquired",
                  old_value: null,
                  new_value: { season_number: 1, ownership: "owned", media: "Blu-ray" },
                  created_at: "2026-07-20T10:00:00Z",
                },
              ],
            }
          : url.includes("/seasons")
            ? { seasons: [], total_seasons: 0, owned_seasons: 0, watched_seasons: 0 }
            : item;
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: "OK",
          json: () => Promise.resolve(body),
        } as Response);
      }),
    );
    renderDetail();

    expect(await screen.findByText("Season 3 watched")).toBeInTheDocument();
    expect(screen.getByText("Season 1 acquired (Blu-ray)")).toBeInTheDocument();
  });

  it("credits TMDB as the metadata source for TV", async () => {
    vi.unstubAllGlobals();
    mockFetch({
      ...GAME,
      type: "tv",
      platform: null,
      metadata: { description: "Nine noble families...", artwork_fetched: true },
    });
    renderDetail();

    expect(await screen.findByText("Metadata via TMDB")).toBeInTheDocument();
  });
});
