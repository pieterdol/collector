import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { describeItem, PosterCard } from "../components/PosterCard";
import type { Item } from "../lib/types";

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
};

function renderCard(item: Item) {
  return render(
    <MemoryRouter>
      <PosterCard item={item} />
    </MemoryRouter>,
  );
}

describe("PosterCard", () => {
  it("links to the item detail page", () => {
    renderCard(base);
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/items/11111111-1111-1111-1111-111111111111",
    );
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
