import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
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

function mockFetch() {
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
            ],
          }
        : url.includes("/api/platforms")
          ? {
              platforms: [
                { id: "p1", name: "Nintendo Switch", abbreviation: null },
                { id: "p2", name: "PlayStation 4", abbreviation: "PS4" },
              ],
            }
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
