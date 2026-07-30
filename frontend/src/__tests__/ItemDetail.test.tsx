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

function renderDetail(state?: Record<string, unknown>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: `/items/${ID}`, state }]}>
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

  it("does not save when the page number is left unchanged", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Edit current page" }));
    fireEvent.blur(screen.getByLabelText("Current page"));

    await waitFor(() => {
      expect(screen.queryByLabelText("Current page")).not.toBeInTheDocument();
    });
    expect(patchBodies(fetchMock)).toHaveLength(0);
  });

  it("describes a total-only change as setting the total", async () => {
    const events = [
      {
        id: "e1",
        event_type: "progress_update",
        old_value: { progress_current: "0.00", progress_total: null },
        new_value: { progress_current: "0.00", progress_total: "412.00" },
        created_at: "2026-07-22T10:00:00Z",
      },
      {
        id: "e2",
        event_type: "progress_update",
        old_value: { progress_current: "100.00", progress_total: "412.00" },
        new_value: { progress_current: "150.00", progress_total: "412.00" },
        created_at: "2026-07-21T10:00:00Z",
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("/activity") ? { events } : BOOK;
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: "OK",
          json: () => Promise.resolve(body),
        } as Response);
      }),
    );
    renderDetail();

    expect(await screen.findByText("Total set to 412 pages")).toBeInTheDocument();
    expect(screen.getByText("Progress 100 → 150")).toBeInTheDocument();
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

describe("ItemDetail scanned notice", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("says you already own it when a scan opened the page", async () => {
    mockFetch(BOOK);
    renderDetail({ scanned: "9780441172719" });

    expect(await screen.findByText("You already own this item.")).toBeInTheDocument();
    expect(screen.getByText("9780441172719")).toBeInTheDocument();
  });

  it("calls a wishlisted copy what it is", async () => {
    mockFetch({ ...BOOK, status: "wishlist" });
    renderDetail({ scanned: "9780441172719" });

    expect(await screen.findByText("This is already on your wishlist.")).toBeInTheDocument();
    expect(screen.queryByText("You already own this item.")).not.toBeInTheDocument();
  });

  it("stays out of the way when the page was opened normally", async () => {
    mockFetch(BOOK);
    renderDetail();

    await screen.findByRole("heading", { name: "Dune" });
    expect(screen.queryByText("You already own this item.")).not.toBeInTheDocument();
  });
});

describe("ItemDetail rename", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renames the item from its heading", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Dune" }));
    const input = screen.getByLabelText("Title");
    fireEvent.change(input, { target: { value: "Dune Messiah" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({ title: "Dune Messiah" });
    });
  });

  it("commits a rename with Enter", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Dune" }));
    const input = screen.getByLabelText("Title");
    fireEvent.change(input, { target: { value: "Dune (SF Masterworks)" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({ title: "Dune (SF Masterworks)" });
    });
  });

  it("trims a rename before saving", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Dune" }));
    const input = screen.getByLabelText("Title");
    fireEvent.change(input, { target: { value: "  Dune  " } });
    fireEvent.blur(input);

    await waitFor(() => expect(screen.queryByLabelText("Title")).not.toBeInTheDocument());
    expect(patchBodies(fetchMock)).toHaveLength(0); // trimmed back to the original
  });

  it("keeps the old title when the field is emptied", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Dune" }));
    const input = screen.getByLabelText("Title");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);

    // An item must have a title — the blank reverts instead of being sent.
    expect(await screen.findByRole("heading", { name: "Dune" })).toBeInTheDocument();
    expect(patchBodies(fetchMock)).toHaveLength(0);
  });

  it("abandons the rename on Escape", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Dune" }));
    const input = screen.getByLabelText("Title");
    fireEvent.change(input, { target: { value: "Duen" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(await screen.findByRole("heading", { name: "Dune" })).toBeInTheDocument();
    expect(patchBodies(fetchMock)).toHaveLength(0);
  });
});

describe("ItemDetail book author", () => {
  afterEach(() => vi.unstubAllGlobals());

  const AUTHORLESS = { ...BOOK, metadata: { artwork_fetched: true } };

  it("offers the author field on a book that has none", async () => {
    mockFetch(AUTHORLESS);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    const row = await screen.findByRole("button", { name: "Edit author" });
    expect(row).toHaveTextContent("Add author…");
    fireEvent.click(row);
    const input = screen.getByLabelText("Author");
    fireEvent.change(input, { target: { value: "Ursula K. Le Guin" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({
        metadata: { artwork_fetched: true, authors: ["Ursula K. Le Guin"] },
      });
    });
  });

  it("splits a comma-separated list into separate authors", async () => {
    mockFetch(AUTHORLESS);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Edit author" }));
    const input = screen.getByLabelText("Author");
    fireEvent.change(input, { target: { value: "Terry Pratchett, Neil Gaiman" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({
        metadata: { artwork_fetched: true, authors: ["Terry Pratchett", "Neil Gaiman"] },
      });
    });
  });

  it("treats an empty authors list as unset", async () => {
    // Manually added books store authors: [] when the field is left blank.
    mockFetch({ ...BOOK, metadata: { authors: [], artwork_fetched: true } });
    renderDetail();

    expect(await screen.findByRole("button", { name: "Edit author" })).toHaveTextContent(
      "Add author…",
    );
  });

  it("keeps the author fixable once it is set", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    const row = await screen.findByRole("button", { name: "Edit author" });
    expect(row).toHaveTextContent("Frank Herbert");
    fireEvent.click(row);
    const input = screen.getByLabelText<HTMLInputElement>("Author");
    expect(input.value).toBe("Frank Herbert");
    fireEvent.change(input, { target: { value: "Frank Patrick Herbert" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({
        metadata: { artwork_fetched: true, authors: ["Frank Patrick Herbert"] },
      });
    });
  });

  it("does not save an unchanged author", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Edit author" }));
    fireEvent.blur(screen.getByLabelText("Author"));

    await waitFor(() => expect(screen.queryByLabelText("Author")).not.toBeInTheDocument());
    expect(patchBodies(fetchMock)).toHaveLength(0);
  });

  it("drops the authors key when the field is cleared", async () => {
    mockFetch(BOOK);
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Edit author" }));
    const input = screen.getByLabelText("Author");
    fireEvent.change(input, { target: { value: "  " } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(patchBodies(fetchMock)).toContainEqual({ metadata: { artwork_fetched: true } });
    });
  });

  it("leaves other types' creators read-only — they can be re-linked", async () => {
    mockFetch({
      ...GAME,
      type: "movie",
      platform: null,
      metadata: { director: "Denis Villeneuve", artwork_fetched: true },
    });
    renderDetail();

    // Twice: the hero subtitle and the Details row — both plain text.
    expect(await screen.findAllByText("Denis Villeneuve")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Edit author" })).not.toBeInTheDocument();
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
    expect(screen.getByText("22-03-2019")).toBeInTheDocument();
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
                {
                  id: "e3",
                  event_type: "season_removed",
                  old_value: { season_number: 7, watched: false },
                  new_value: null,
                  created_at: "2026-07-19T10:00:00Z",
                },
                {
                  id: "e4",
                  event_type: "episode_watched",
                  old_value: { season_number: 2, episode_number: 4, watched: false },
                  new_value: { season_number: 2, episode_number: 4, watched: true },
                  created_at: "2026-07-18T10:00:00Z",
                },
                {
                  id: "e5",
                  event_type: "episode_watched",
                  old_value: { season_number: 2, episode_number: 5, watched: true },
                  new_value: { season_number: 2, episode_number: 5, watched: false },
                  created_at: "2026-07-17T10:00:00Z",
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
    expect(screen.getByText("Season 7 removed")).toBeInTheDocument();
    expect(screen.getByText("S2E4 watched")).toBeInTheDocument();
    expect(screen.getByText("S2E5 unwatched")).toBeInTheDocument();
  });

  it("shows the TMDB rating for movies and TV", async () => {
    vi.unstubAllGlobals();
    mockFetch({
      ...GAME,
      type: "movie",
      platform: null,
      metadata: { tmdb_rating: 8.5, artwork_fetched: true },
    });
    renderDetail();

    expect(await screen.findByText("TMDB rating")).toBeInTheDocument();
    expect(screen.getByText("8.5 / 10")).toBeInTheDocument();
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

const RECORD = {
  ...GAME,
  type: "music",
  platform: null,
  status: "completed",
  title: "Kid A",
  metadata: {
    artist: "Radiohead",
    year: 2000,
    release_date: "2000-10-02",
    label: "Parlophone",
    catalog_number: "7243 5 27753 1 4",
    country: "GB",
    release_type: "Album",
    media: 'Vinyl 12"',
    barcode: "724352773824",
    mb_release_id: "b1392450-e666-3926-a536-22c65f834433",
    track_count: 2,
    tracks: [
      { position: "A1", title: "Everything in Its Right Place", length: "4:11" },
      { position: "A2", title: "Kid A", length: "4:44" },
    ],
    artwork_fetched: true,
  },
};

describe("ItemDetail music", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the pressing details a record is identified by", async () => {
    mockFetch(RECORD);
    renderDetail();

    expect(await screen.findByText("Artist")).toBeInTheDocument();
    expect(screen.getByText("Radiohead")).toBeInTheDocument();
    expect(screen.getByText("Label")).toBeInTheDocument();
    expect(screen.getByText("Parlophone")).toBeInTheDocument();
    expect(screen.getByText("Catalogue number")).toBeInTheDocument();
    expect(screen.getByText("7243 5 27753 1 4")).toBeInTheDocument();
    expect(screen.getByText("724352773824")).toBeInTheDocument();
  });

  it("lists the tracklist with side positions and lengths", async () => {
    mockFetch(RECORD);
    renderDetail();

    expect(await screen.findByText("Tracklist")).toBeInTheDocument();
    expect(screen.getByText("Everything in Its Right Place")).toBeInTheDocument();
    expect(screen.getByText("A1")).toBeInTheDocument();
    expect(screen.getByText("4:11")).toBeInTheDocument();
  });

  it("offers the carrier select for a physical record", async () => {
    mockFetch(RECORD);
    renderDetail();

    const media = await screen.findByLabelText<HTMLSelectElement>("Media");
    expect(media.value).toBe('Vinyl 12"');
    expect([...media.options].map((o) => o.text)).toContain("Vinyl LP");
  });

  it("credits the catalog the record was matched in", async () => {
    mockFetch({ ...RECORD, metadata: { ...RECORD.metadata, description: "Fourth album." } });
    renderDetail();

    expect(await screen.findByText(/Metadata via MusicBrainz/)).toBeInTheDocument();
  });

  it("credits Discogs when that is where the match came from", async () => {
    mockFetch({
      ...RECORD,
      metadata: {
        ...RECORD.metadata,
        mb_release_id: undefined,
        discogs_release_id: 371000,
        description: "Fourth album.",
      },
    });
    renderDetail();

    expect(await screen.findByText(/Metadata via Discogs/)).toBeInTheDocument();
  });

  it("does not chase artwork that music catalogs do not carry", async () => {
    mockFetch({ ...RECORD, metadata: { ...RECORD.metadata, artwork_fetched: false } });
    renderDetail();

    // By title, not by text: "Kid A" is also a track on it.
    await screen.findByRole("heading", { name: "Kid A" });
    await waitFor(() =>
      expect(
        (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([u]) =>
          String(u).includes("/artwork"),
        ),
      ).toHaveLength(0),
    );
  });

  it("has no progress panel — an album is not read page by page", async () => {
    mockFetch({ ...RECORD, status: "in_progress" });
    renderDetail();

    await screen.findByRole("heading", { name: "Kid A" });
    expect(screen.queryByText("Progress")).not.toBeInTheDocument();
    expect(screen.queryByText("Play time")).not.toBeInTheDocument();
  });
});

describe("ItemDetail back link", () => {
  beforeEach(() => mockFetch());
  afterEach(() => vi.unstubAllGlobals());

  it("returns to the library by default", async () => {
    renderDetail();
    const link = await screen.findByRole("link", { name: /library/i });
    expect(link).toHaveAttribute("href", "/");
  });

  it("returns to Upcoming when the item was opened from the upcoming page", async () => {
    renderDetail({ from: "upcoming" });
    const link = await screen.findByRole("link", { name: /upcoming/i });
    expect(link).toHaveAttribute("href", "/upcoming");
    expect(screen.queryByRole("link", { name: /library/i })).not.toBeInTheDocument();
  });
});

describe("ItemDetail relink", () => {
  afterEach(() => vi.unstubAllGlobals());

  function mockRelinkFetch() {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("/api/enrich/search")
          ? {
              provider: "igdb",
              available: true,
              results: [
                {
                  title: "Sekiro: Shadows Die Twice",
                  type: "game",
                  metadata: { year: 2019, developer: "FromSoftware" },
                  cover_url: null,
                  external_id: "9630",
                },
              ],
            }
          : url.includes("/activity")
            ? { events: [] }
            : GAME;
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: "OK",
          json: () => Promise.resolve(body),
        } as Response);
      }),
    );
  }

  it("searches the catalog and relinks the picked record", async () => {
    mockRelinkFetch();
    renderDetail();

    fireEvent.click(await screen.findByRole("button", { name: "Re-link…" }));
    expect(screen.getByLabelText("Search catalog")).toHaveValue("Sekiro: Shadows Die Twice");

    const option = await screen.findByRole("button", { name: /FromSoftware/ });
    fireEvent.click(option);

    await waitFor(() => {
      const call = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(([u]) =>
        String(u).includes("/relink"),
      );
      expect(call).toBeDefined();
      expect((call![1] as RequestInit).method).toBe("POST");
      expect(JSON.parse(String((call![1] as RequestInit).body))).toEqual({
        external_id: "9630",
      });
    });
  });
});
