import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Wishlist from "../pages/Wishlist";

const ITEMS = [
  {
    id: "movie-1",
    type: "movie",
    status: "wishlist",
    title: "Wished movie",
    metadata: {},
    cover_path: "covers/movie-1.jpg",
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

function renderWishlist() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/wishlist"]}>
        <Wishlist />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Wishlist page", () => {
  beforeEach(() => {
    mockFetch();
    HTMLDialogElement.prototype.showModal = vi.fn();
    HTMLDialogElement.prototype.close = vi.fn();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the poster clickable through to the detail page", async () => {
    renderWishlist();
    const link = (await screen.findByText("Wished movie")).closest("a");
    expect(link).toHaveAttribute("href", "/items/movie-1");
  });

  it("hides the acquire overlay on mobile widths instead of pinning it open", async () => {
    renderWishlist();
    const button = await screen.findByRole("button", { name: "Acquire" });
    // Below the mobile breakpoint there is no hover, so the overlay must be
    // removed from the layer entirely — an opacity-0 button would still swallow
    // taps meant for the poster.
    expect(button.className).toContain("max-[820px]:hidden");
    expect(button.className).not.toContain("max-[820px]:opacity-100");
  });

  it("opens the acquire dialog from the hover overlay", async () => {
    renderWishlist();
    fireEvent.click(await screen.findByRole("button", { name: "Acquire" }));
    expect(await screen.findByText("Acquired: Wished movie")).toBeInTheDocument();
  });
});
