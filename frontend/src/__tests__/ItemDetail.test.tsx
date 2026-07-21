import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const BOOK = {
  ...GAME,
  type: "book",
  platform: null,
  status: "in_progress",
  title: "Dune",
  metadata: { authors: ["Frank Herbert"], artwork_fetched: true },
  progress_current: "100",
  progress_total: "400",
};

function patchBodies(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "PATCH")
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
}

describe("ItemDetail book progress", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lets you type the current page from the p. line", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Edit current page" }));
    const input = screen.getByLabelText("Current page");
    fireEvent.change(input, { target: { value: "150" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({ progress_current: 150 });
    });
  });

  it("shows ? for an unknown total and lets you set it inline", async () => {
    mockFetch({ ...BOOK, progress_total: null });
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    const totalButton = await screen.findByRole("button", { name: "Edit total pages" });
    expect(totalButton).toHaveTextContent("?");
    fireEvent.click(totalButton);
    const input = screen.getByLabelText("Total pages");
    fireEvent.change(input, { target: { value: "400" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({ progress_total: 400 });
    });
  });
});

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

  it("locks the release date for a game once it is set", async () => {
    vi.unstubAllGlobals();
    mockFetch({
      ...GAME,
      metadata: { ...GAME.metadata, release_date: "2019-03-22" },
    });
    renderDetail();

    expect(await screen.findByText("Released")).toBeInTheDocument();
    expect(screen.queryByLabelText("Release date")).not.toBeInTheDocument();
    expect(screen.getByText("Mar 22, 2019")).toBeInTheDocument();
  });

  it("keeps the release date editable while it is unset", async () => {
    renderDetail(); // default GAME has no release_date

    expect(await screen.findByLabelText("Release date")).toBeInTheDocument();
  });

  it("keeps the release date editable for books even when set", async () => {
    vi.unstubAllGlobals();
    mockFetch({
      ...GAME,
      type: "book",
      platform: null,
      metadata: { release_date: "1965-08-01", artwork_fetched: true },
    });
    renderDetail();

    expect(await screen.findByLabelText("Release date")).toBeInTheDocument();
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
