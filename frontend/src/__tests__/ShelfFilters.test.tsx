import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Shelf from "../pages/Shelf";

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/items/platforms")
        ? { platforms: ["PC (Microsoft Windows)", "PlayStation 4", "Xbox One"] }
        : url.includes("/api/stats")
          ? { tiles: {}, continue: [], loans: [], recent: [] }
          : { items: [], total: 0 };
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve(body),
      } as Response);
    }),
  );
}

function itemCalls(): string[] {
  return (fetch as ReturnType<typeof vi.fn>).mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/api/items?"));
}

function renderShelf(initialEntry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Shelf />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Shelf mobile filter grouping", () => {
  beforeEach(() => mockFetch());
  afterEach(() => vi.unstubAllGlobals());

  it("collapses the selects behind a Filters toggle", async () => {
    renderShelf("/?type=game");
    const toggle = await screen.findByRole("button", { name: /^filters/i });
    expect(screen.queryByRole("group", { name: /filter options/i })).not.toBeInTheDocument();

    fireEvent.click(toggle);
    const panel = screen.getByRole("group", { name: /filter options/i });
    expect(within(panel).getByLabelText("Platform")).toBeInTheDocument();
    expect(within(panel).getByLabelText("Status")).toBeInTheDocument();
    expect(within(panel).getByLabelText("Sort")).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.queryByRole("group", { name: /filter options/i })).not.toBeInTheDocument();
  });

  it("shows how many filters are active on the toggle", async () => {
    renderShelf("/?type=game&status=completed&platform=PlayStation+4");
    const toggle = await screen.findByRole("button", { name: /^filters/i });
    expect(toggle.textContent).toContain("2");
  });

  it("offers the type chips as a compact select too", async () => {
    renderShelf("/?type=game");
    const select = await screen.findByLabelText<HTMLSelectElement>("Type");
    expect(select.value).toBe("game");

    fireEvent.change(select, { target: { value: "movie" } });
    await waitFor(() => expect(itemCalls().some((url) => url.includes("type=movie"))).toBe(true));
  });

  it("filters from inside the panel refetch the list", async () => {
    renderShelf("/?type=game");
    fireEvent.click(await screen.findByRole("button", { name: /^filters/i }));
    const panel = screen.getByRole("group", { name: /filter options/i });

    fireEvent.change(within(panel).getByLabelText("Status"), { target: { value: "backlog" } });
    await waitFor(() =>
      expect(itemCalls().some((url) => url.includes("status=backlog"))).toBe(true),
    );
  });
});
