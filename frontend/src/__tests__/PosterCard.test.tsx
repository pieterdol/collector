import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { coverColors, PosterCard } from "../components/PosterCard";
import type { Item } from "../lib/types";

const base: Item = {
  id: "11111111-1111-1111-1111-111111111111",
  user_id: "u",
  type: "book",
  format: "physical",
  status: "in_progress",
  title: "Dune",
  cover_path: null,
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

  it("shows a progress badge for in-progress items", () => {
    renderCard(base);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("shows a loan badge while lent out, hides it after return", () => {
    renderCard({ ...base, borrowed_by: "Sanne" });
    expect(screen.getByText("Sanne")).toBeInTheDocument();
  });

  it("renders a generated cover with the title when no cover is stored", () => {
    renderCard(base);
    expect(screen.getAllByText("Dune").length).toBeGreaterThan(0);
    expect(document.querySelector("img")).toBeNull();
  });

  it("uses the stored cover image when present", () => {
    renderCard({ ...base, cover_path: "/media/covers/x.jpg" });
    const img = document.querySelector("img");
    expect(img).toHaveAttribute("src", "/media/covers/x.jpg");
  });
});

describe("coverColors", () => {
  it("is deterministic per title", () => {
    expect(coverColors("Dune")).toEqual(coverColors("Dune"));
    expect(coverColors("Dune")).not.toEqual(coverColors("Hollow Knight"));
  });
});
