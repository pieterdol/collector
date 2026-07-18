import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AddItem from "../pages/AddItem";

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
              { name: "igdb", type: "game", available: true },
            ],
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
