import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AddItem from "../pages/AddItem";

const SEKIRO = {
  title: "Sekiro: Shadows Die Twice",
  type: "game",
  metadata: {
    developer: "FromSoftware",
    year: 2019,
    platform: "Google Stadia, PlayStation 4, PC (Microsoft Windows), Xbox One",
  },
  cover_url: "https://images.igdb.com/covers/t_cover_big/sekiro.jpg",
  external_id: "9617",
};

const KID_A = {
  title: "Kid A",
  type: "music",
  metadata: {
    artist: "Radiohead",
    year: 2000,
    media: 'Vinyl 12"',
    label: "Parlophone",
    catalog_number: "7243 5 27753 1 4",
    track_count: 10,
  },
  cover_url: "https://coverartarchive.org/release/kid-a/front-500",
  external_id: "mb:b1392450-e666-3926-a536-22c65f834433",
};

function mockFetch(musicProvider = "musicbrainz") {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/enrich/providers")
        ? {
            providers: [
              { name: "openlibrary", type: "book", available: true },
              { name: "tmdb", type: "movie", available: true },
              { name: "tmdb", type: "tv", available: true },
              { name: "igdb", type: "game", available: true },
              // Keyless MusicBrainz unless a Discogs token is configured.
              { name: musicProvider, type: "music", available: true },
            ],
          }
        : url.includes("/api/platforms")
          ? {
              platforms: [
                { id: "p1", name: "Nintendo Switch", abbreviation: null },
                { id: "p2", name: "PlayStation 4", abbreviation: "PS4" },
                // Catalog rows arrive alphabetically — an A-name here proves
                // the pinned block isn't just riding on IGDB's own order.
                { id: "p3", name: "Atari 2600", abbreviation: null },
                { id: "p4", name: "Xbox", abbreviation: "XBOX" },
              ],
            }
          : url.includes("type=music")
            ? { provider: musicProvider, available: true, results: [KID_A] }
            : url.includes("type=game")
              ? {
                  provider: "igdb",
                  available: true,
                  // Sekiro never came out on Switch: the filter empties the list.
                  results: url.includes("platform=Nintendo+Switch") ? [] : [SEKIRO],
                }
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

function searchCalls(): string[] {
  return (fetch as ReturnType<typeof vi.fn>).mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/api/enrich/search"));
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AddItem />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AddItem search debounce", () => {
  beforeEach(() => mockFetch());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("sends one request for the final query, not one per keystroke", async () => {
    renderPage();
    const input = await screen.findByPlaceholderText(/Search Open Library/);

    vi.useFakeTimers();
    for (const q of ["d", "du", "dun", "dune"]) {
      fireEvent.change(input, { target: { value: q } });
      // Fast typing: well within the 300ms window, but with rendering and
      // microtasks flushing between keystrokes like in a real browser.
      await act(() => vi.advanceTimersByTimeAsync(100));
    }
    await act(() => vi.advanceTimersByTimeAsync(1000)); // let the debounce settle
    vi.useRealTimers();

    expect(searchCalls()).toHaveLength(1);
    expect(searchCalls()[0]).toContain("q=dune");
  });

  it("debounces the game search too", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    const input = await screen.findByPlaceholderText(/Search IGDB/);

    vi.useFakeTimers();
    for (const q of ["se", "sek", "seki", "sekiro"]) {
      fireEvent.change(input, { target: { value: q } });
      await act(() => vi.advanceTimersByTimeAsync(100));
    }
    await act(() => vi.advanceTimersByTimeAsync(1000));
    vi.useRealTimers();

    expect(searchCalls()).toHaveLength(1);
    expect(searchCalls()[0]).toContain("q=sekiro");
  });

  it("does not fire on the pauses of an ordinary typing speed", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    const input = await screen.findByPlaceholderText(/Search IGDB/);

    vi.useFakeTimers();
    for (const q of ["se", "sek", "seki", "sekiro"]) {
      fireEvent.change(input, { target: { value: q } });
      // A hunt-and-peck 350ms between keys — that's still one search, not four.
      await act(() => vi.advanceTimersByTimeAsync(350));
    }
    await act(() => vi.advanceTimersByTimeAsync(1000));
    vi.useRealTimers();

    expect(searchCalls()).toHaveLength(1);
    expect(searchCalls()[0]).toContain("q=sekiro");
  });

  it("does not search queries shorter than two characters", async () => {
    renderPage();
    const input = await screen.findByPlaceholderText(/Search Open Library/);

    vi.useFakeTimers();
    fireEvent.change(input, { target: { value: "d" } });
    await act(() => vi.advanceTimersByTimeAsync(1000));
    vi.useRealTimers();

    expect(searchCalls()).toHaveLength(0);
  });
});

describe("retyping a search", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  /** Like mockFetch, but the follow-up term's request never resolves. */
  function mockSlowSecondSearch() {
    const json = (body: unknown) =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve(body),
      } as Response);
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/enrich/providers")) {
          return json({ providers: [{ name: "igdb", type: "game", available: true }] });
        }
        if (url.includes("/api/platforms")) return json({ platforms: [] });
        if (url.includes("q=Sekiro+2")) return new Promise<Response>(() => {}); // in flight
        return json({ provider: "igdb", available: true, results: [SEKIRO] });
      }),
    );
  }

  it("keeps the results on screen while the next term is still loading", async () => {
    mockSlowSecondSearch();
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    const input = await screen.findByPlaceholderText(/Search IGDB/);
    fireEvent.change(input, { target: { value: "Sekiro" } });
    await screen.findByText("Sekiro: Shadows Die Twice");

    fireEvent.change(input, { target: { value: "Sekiro 2" } });
    await waitFor(() =>
      expect(searchCalls().some((url) => url.includes("q=Sekiro+2"))).toBe(true),
    );

    // The list must not blank out between terms — that reads as a broken search.
    expect(screen.getByText("Sekiro: Shadows Die Twice")).toBeInTheDocument();
  });

  it("drops the results when the box is cleared", async () => {
    mockSlowSecondSearch();
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    const input = await screen.findByPlaceholderText(/Search IGDB/);
    fireEvent.change(input, { target: { value: "Sekiro" } });
    await screen.findByText("Sekiro: Shadows Die Twice");

    fireEvent.change(input, { target: { value: "" } });
    await waitFor(() =>
      expect(screen.queryByText("Sekiro: Shadows Die Twice")).toBeNull(),
    );
  });
});

describe("game platform options", () => {
  beforeEach(() => mockFetch());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  async function pickSekiro() {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    const input = await screen.findByPlaceholderText(/Search IGDB/);
    fireEvent.change(input, { target: { value: "Sekiro" } });
    fireEvent.click(await screen.findByText("Sekiro: Shadows Die Twice"));
    return screen.findByLabelText<HTMLSelectElement>(/Platform/);
  }

  it("offers only the platforms the found game was released on", async () => {
    const select = await pickSekiro();
    const options = [...select.options].map((o) => o.text);
    expect(options).toContain("PlayStation 4");
    expect(options).toContain("Google Stadia");
    expect(options).toContain("Xbox One");
    expect(options).toContain("Other…");
    expect(options).not.toContain("Nintendo Switch");
  });

  it("keeps the full catalog for manual entry", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    fireEvent.click(screen.getByRole("tab", { name: /manual/i }));
    const select = await screen.findByLabelText<HTMLSelectElement>(/Platform/);
    const options = [...select.options].map((o) => o.text);
    expect(options).toContain("Nintendo Switch");
    expect(options).toContain("Xbox Series X|S");
  });

  it("pins the consoles you actually own above the alphabetical catalog", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    fireEvent.click(screen.getByRole("tab", { name: /manual/i }));
    const select = await screen.findByLabelText<HTMLSelectElement>(/Platform/);
    // The pinned block paints before the catalog request lands; wait for a
    // catalog-only name, or the ordering below compares against nothing.
    await screen.findByRole("option", { name: "Atari 2600" });
    const options = [...select.options].map((o) => o.text);
    // The original Xbox is one row among 200+; alphabetically it lands at the
    // very bottom, which is no use when it's a console you collect for.
    expect(options).toContain("Xbox");
    expect(options).toContain("Xbox 360");
    expect(options.indexOf("Xbox")).toBeLessThan(options.indexOf("Atari 2600"));
    expect(options.indexOf("Xbox 360")).toBeLessThan(options.indexOf("Atari 2600"));
    // ...and they stay with the rest of the Xbox family, newest first,
    // rather than jumping above Windows.
    expect(options.indexOf("Xbox 360")).toBeGreaterThan(options.indexOf("Xbox One"));
    expect(options.indexOf("Xbox")).toBeGreaterThan(options.indexOf("Xbox 360"));
  });
});

describe("game platform filter", () => {
  beforeEach(() => mockFetch());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("narrows the catalog search to the chosen platform", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    fireEvent.change(await screen.findByLabelText("Filter by platform"), {
      target: { value: "PlayStation 4" },
    });
    fireEvent.change(await screen.findByPlaceholderText(/Search IGDB/), {
      target: { value: "Sekiro" },
    });
    await screen.findByText("Sekiro: Shadows Die Twice");

    expect(searchCalls().some((url) => url.includes("platform=PlayStation+4"))).toBe(true);
  });

  it("preselects that platform on the confirm step", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    fireEvent.change(await screen.findByLabelText("Filter by platform"), {
      target: { value: "PlayStation 4" },
    });
    fireEvent.change(await screen.findByPlaceholderText(/Search IGDB/), {
      target: { value: "Sekiro" },
    });
    fireEvent.click(await screen.findByText("Sekiro: Shadows Die Twice"));

    const select = await screen.findByLabelText<HTMLSelectElement>("Platform");
    expect(select.value).toBe("PlayStation 4");
  });

  it("blames the filter when it empties the results", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    fireEvent.change(await screen.findByLabelText("Filter by platform"), {
      target: { value: "Nintendo Switch" },
    });
    fireEvent.change(await screen.findByPlaceholderText(/Search IGDB/), {
      target: { value: "Sekiro" },
    });

    expect(
      await screen.findByText(/on Nintendo Switch/, { selector: "p" }),
    ).toBeInTheDocument();
  });

  it("is not offered for books", async () => {
    renderPage();
    await screen.findByPlaceholderText(/Search Open Library/);
    expect(screen.queryByLabelText("Filter by platform")).toBeNull();
  });
});

describe("going back to the results", () => {
  beforeEach(() => mockFetch());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("keeps the search term and its results", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    fireEvent.change(await screen.findByPlaceholderText(/Search IGDB/), {
      target: { value: "Sekiro" },
    });
    fireEvent.click(await screen.findByText("Sekiro: Shadows Die Twice"));
    fireEvent.click(await screen.findByRole("button", { name: /results/ }));

    expect(await screen.findByPlaceholderText(/Search IGDB/)).toHaveValue("Sekiro");
    expect(await screen.findByText("Sekiro: Shadows Die Twice")).toBeInTheDocument();
  });
});

describe("confirm form", () => {
  beforeEach(() => mockFetch());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("shows the fetched cover on the confirm step", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    const input = await screen.findByPlaceholderText(/Search IGDB/);
    fireEvent.change(input, { target: { value: "Sekiro" } });
    fireEvent.click(await screen.findByText("Sekiro: Shadows Die Twice"));

    const cover = await screen.findByAltText("Cover of Sekiro: Shadows Die Twice");
    expect(cover).toHaveAttribute(
      "src",
      "https://images.igdb.com/covers/t_cover_big/sekiro.jpg",
    );
  });

  it("sends no platform at all when you skip the picker", async () => {
    // The catalog's `platform` is every console the game shipped on, joined
    // with commas. Passing that through made the backend mint a platform
    // named after four consoles at once; the list belongs in released_on.
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /game/i }));
    const input = await screen.findByPlaceholderText(/Search IGDB/);
    fireEvent.change(input, { target: { value: "Sekiro" } });
    fireEvent.click(await screen.findByText("Sekiro: Shadows Die Twice"));
    fireEvent.click(await screen.findByRole("button", { name: /Add to shelf/ }));

    const posted = () =>
      (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/api/items") && (init as RequestInit)?.method === "POST",
      );
    await waitFor(() => expect(posted()).toBeDefined());
    const sent = JSON.parse(String((posted()![1] as RequestInit).body));
    expect(sent.metadata).not.toHaveProperty("platform");
    expect(sent.metadata.released_on).toEqual([
      "Google Stadia",
      "PlayStation 4",
      "PC (Microsoft Windows)",
      "Xbox One",
    ]);
  });
});

describe("TV type", () => {
  beforeEach(() => mockFetch());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("is a selectable type backed by TMDB", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /tv/i }));
    expect(await screen.findByPlaceholderText(/Search TMDB/)).toBeInTheDocument();
  });

  it("offers the disc-media select for physical TV in manual entry", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /tv/i }));
    fireEvent.click(screen.getByRole("tab", { name: /manual/i }));
    const media = await screen.findByLabelText<HTMLSelectElement>("Media");
    const options = [...media.options].map((o) => o.text);
    expect(options).toContain("Blu-ray");
    expect(options).toContain("Ultra HD Blu-ray");
  });
});

describe("Music type", () => {
  beforeEach(() => mockFetch());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  async function searchKidA() {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /music/i }));
    fireEvent.change(await screen.findByPlaceholderText(/Search MusicBrainz/), {
      target: { value: "kid a" },
    });
    // The whole result row, so its pressing line is in scope too.
    return (await screen.findByText("Kid A")).closest("button")!;
  }

  it("is a selectable type backed by MusicBrainz, no key needed", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /music/i }));
    expect(await screen.findByPlaceholderText(/Search MusicBrainz/)).toBeInTheDocument();
  });

  it("shows the pressing that tells two editions apart", async () => {
    const row = await searchKidA();
    // Artist, year, carrier and label are what distinguish one pressing
    // of an album from another — a bare title is useless here.
    expect(row).toHaveTextContent("Radiohead");
    expect(row).toHaveTextContent("2000");
    expect(row).toHaveTextContent('Vinyl 12"');
    expect(row).toHaveTextContent("Parlophone");
  });

  it("labels the creator field Artist and the count Tracks", async () => {
    fireEvent.click(await searchKidA());
    expect(await screen.findByLabelText<HTMLInputElement>("Artist")).toHaveValue("Radiohead");
    expect(screen.getByLabelText<HTMLInputElement>("Tracks")).toHaveValue("10");
  });

  it("offers the carrier select for a physical record, prefilled from the catalog", async () => {
    fireEvent.click(await searchKidA());
    const media = await screen.findByLabelText<HTMLSelectElement>("Media");
    expect(media.value).toBe('Vinyl 12"');
    const options = [...media.options].map((o) => o.text);
    expect(options).toContain("Vinyl LP");
    expect(options).toContain('Vinyl 7"');
    expect(options).toContain("CD");
    expect(options).toContain("Cassette");
    // Disc formats belong to films, not records.
    expect(options).not.toContain("Blu-ray");
  });

  it("offers barcode scanning, because sleeves are in the catalogs", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /music/i }));
    expect(screen.getByRole("tab", { name: /scan barcode/i })).toBeInTheDocument();
  });
});

describe("Music with a Discogs token", () => {
  beforeEach(() => mockFetch("discogs"));
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("names the catalog actually in use", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /music/i }));
    expect(await screen.findByPlaceholderText(/Search Discogs/)).toBeInTheDocument();
  });
});
