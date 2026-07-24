import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Upcoming from "../pages/Upcoming";

function futureIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const ITEMS = [
  {
    id: "game-1",
    type: "game",
    status: "backlog",
    title: "Preordered game",
    metadata: { release_date: futureIso(3) },
    cover_path: null,
    platform: null,
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
  },
  {
    id: "movie-1",
    type: "movie",
    status: "wishlist",
    title: "Wished movie",
    metadata: { release_date: futureIso(10) },
    cover_path: null,
    platform: null,
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
  },
];

function mockFetch(items: unknown[] = ITEMS) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve({ items, total: items.length }),
      } as Response),
    ),
  );
}

function itemCalls(): string[] {
  return (fetch as ReturnType<typeof vi.fn>).mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/api/items?"));
}

function renderUpcoming(initialEntry = "/upcoming") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Upcoming />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Upcoming page", () => {
  beforeEach(() => mockFetch());
  afterEach(() => vi.unstubAllGlobals());

  it("requests upcoming items sorted by release", async () => {
    renderUpcoming();
    await screen.findByText("Preordered game");
    expect(itemCalls()[0]).toContain("upcoming=true");
    expect(itemCalls()[0]).toContain("sort=release");
  });

  it("tags wishlist rows and counts all upcoming items", async () => {
    renderUpcoming();
    await screen.findByText("Wished movie");
    expect(screen.getByText("2 upcoming")).toBeInTheDocument();
    expect(screen.getAllByText("wishlist")).toHaveLength(1);
  });

  it("links rows to the item detail with an upcoming origin", async () => {
    renderUpcoming();
    const link = (await screen.findByText("Preordered game")).closest("a");
    expect(link).toHaveAttribute("href", "/items/game-1");
  });

  it("filters by type through the chip row", async () => {
    renderUpcoming();
    await screen.findByText("Preordered game");
    fireEvent.click(screen.getByRole("button", { name: "Games" }));
    const last = itemCalls().at(-1)!;
    expect(last).toContain("type=game");
  });

  it("shows the empty state when nothing is upcoming", async () => {
    mockFetch([]);
    renderUpcoming();
    expect(await screen.findByText("Nothing on the horizon")).toBeInTheDocument();
  });
});
