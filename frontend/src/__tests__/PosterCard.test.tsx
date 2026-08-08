import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { describeItem, PosterCard } from "../components/PosterCard";
import type { Item } from "../lib/types";

function LocationSpy() {
  const location = useLocation();
  return <div data-testid="loc">{location.pathname + location.search}</div>;
}

const base: Item = {
  id: "11111111-1111-1111-1111-111111111111",
  user_id: "u",
  type: "book",
  format: "physical",
  status: "in_progress",
  title: "Dune",
  cover_path: null,
  platform: null,
  metadata: { authors: ["Frank Herbert"], year: 1965 },
  progress_current: "206",
  progress_total: "412",
  rating: "4.5",
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
  bundle_id: null,
  bundle_front: false,
  bundle_count: 1,
  bundle_labels: [],
};

function renderCard(item: Item) {
  return render(
    <MemoryRouter>
      <PosterCard item={item} />
      <LocationSpy />
    </MemoryRouter>,
  );
}

function FromSpy() {
  const location = useLocation();
  return <div data-testid="from">{(location.state as { from?: string } | null)?.from ?? ""}</div>;
}

describe("PosterCard", () => {
  it("links to the item detail page", () => {
    renderCard(base);
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/items/11111111-1111-1111-1111-111111111111",
    );
  });

  it("carries the filtered list it was opened from", () => {
    // The detail page reads this to send you back to the same view.
    render(
      <MemoryRouter initialEntries={["/?type=game&platform=Xbox+360"]}>
        <PosterCard item={base} />
        <FromSpy />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("link"));
    expect(screen.getByTestId("from")).toHaveTextContent("/?type=game&platform=Xbox+360");
  });

  it("shows the status badge on the cover", () => {
    renderCard(base);
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("shows the progress strip for in-progress items", () => {
    renderCard(base);
    expect(screen.getByTitle("206 / 412")).toBeInTheDocument();
  });

  it("shows a loan badge while lent out", () => {
    renderCard({ ...base, borrowed_by: "Sanne" });
    expect(screen.getByText("→ Sanne")).toBeInTheDocument();
  });

  it("hides the loan badge once returned", () => {
    renderCard({ ...base, borrowed_by: "Sanne", returned_date: "2026-07-01" });
    expect(screen.queryByText("→ Sanne")).not.toBeInTheDocument();
  });

  it("renders a placeholder with the title when no cover is stored", () => {
    renderCard(base);
    expect(screen.getAllByText("Dune").length).toBeGreaterThan(0);
    expect(document.querySelector("img")).toBeNull();
  });

  it("uses the stored cover image when present", () => {
    renderCard({ ...base, cover_path: "/media/covers/x.jpg" });
    const img = document.querySelector("img");
    expect(img?.getAttribute("src")).toContain("/media/covers/x.jpg?v=");
  });

  it("shows the disc-format badge for physical movies", () => {
    renderCard({ ...base, type: "movie", metadata: { media: "Ultra HD Blu-ray" } });
    expect(screen.getByTitle("Ultra HD Blu-ray")).toHaveTextContent("4K");
  });

  it("shows the platform badge for games", () => {
    renderCard({ ...base, type: "game", platform: "PlayStation 5" });
    expect(screen.getByTitle("PlayStation 5")).toHaveTextContent("PS5");
  });

  it("clicking the platform badge filters the library on that platform", () => {
    renderCard({ ...base, type: "game", platform: "PlayStation 5" });
    fireEvent.click(screen.getByTitle("PlayStation 5"));
    expect(screen.getByTestId("loc").textContent).toBe("/?type=game&platform=PlayStation%205");
  });

  it("clicking the disc badge filters the library on that media", () => {
    renderCard({ ...base, type: "movie", metadata: { media: "Blu-ray" } });
    fireEvent.click(screen.getByTitle("Blu-ray"));
    expect(screen.getByTestId("loc").textContent).toBe("/?type=movie&media=Blu-ray");
  });

  it("shows the disc badge for physical TV and deep-links to the TV type", () => {
    renderCard({ ...base, type: "tv", metadata: { media: "DVD" } });
    fireEvent.click(screen.getByTitle("DVD"));
    expect(screen.getByTestId("loc").textContent).toBe("/?type=tv&media=DVD");
  });

  it("badges a collapsed bundle with how many copies it stands for", () => {
    renderCard({ ...base, bundle_id: "b1", bundle_front: true, bundle_count: 3 });
    expect(screen.getByTitle("3 copies")).toHaveTextContent("3");
  });

  it("leaves an unbundled item unbadged", () => {
    renderCard(base);
    expect(screen.queryByTitle(/copies/)).not.toBeInTheDocument();
  });

  it("names the copies instead of the meta line for a bundle", () => {
    renderCard({
      ...base,
      type: "game",
      platform: "PlayStation 5",
      metadata: { developer: "FromSoftware", year: 2022 },
      bundle_id: "b1",
      bundle_front: true,
      bundle_count: 2,
      bundle_labels: ["PlayStation 5", "PC (Microsoft Windows)"],
    });
    expect(screen.getByText("PS5 · PC")).toBeInTheDocument();
    expect(screen.queryByText(/FromSoftware/)).not.toBeInTheDocument();
  });

  it("falls back to the normal meta line when a bundle has nothing to tell apart", () => {
    renderCard({ ...base, bundle_id: "b1", bundle_front: true, bundle_count: 2 });
    expect(screen.getByText("Frank Herbert · 1965")).toBeInTheDocument();
  });

  it("spells out disc formats of a bundled movie", () => {
    renderCard({
      ...base,
      type: "movie",
      metadata: { media: "DVD" },
      bundle_id: "b1",
      bundle_front: true,
      bundle_count: 2,
      bundle_labels: ["DVD", "Blu-ray"],
    });
    expect(screen.getByText("DVD · Blu-ray")).toBeInTheDocument();
  });
});

describe("describeItem", () => {
  it("builds a compact meta line", () => {
    expect(describeItem(base)).toBe("Frank Herbert · 1965");
  });

  it("uses developer and platform for games", () => {
    expect(
      describeItem({
        ...base,
        type: "game",
        platform: "Switch",
        metadata: { developer: "Team Cherry", year: 2017 },
      }),
    ).toBe("Team Cherry · 2017");
  });
});
