import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ItemTable } from "../components/ItemTable";
import type { Item } from "../lib/types";

const ITEM: Item = {
  id: "22222222-2222-2222-2222-222222222222",
  user_id: "u",
  type: "game",
  format: "physical",
  status: "backlog",
  title: "Halo: Combat Evolved",
  cover_path: null,
  platform: "Xbox",
  metadata: { year: 2001 },
  progress_current: null,
  progress_total: null,
  rating: null,
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

function Spy() {
  const location = useLocation();
  return (
    <div data-testid="nav">
      {location.pathname}|{(location.state as { from?: string } | null)?.from ?? ""}
    </div>
  );
}

describe("ItemTable", () => {
  it("opens the row and remembers the filtered list it came from", () => {
    // The table view is the other half of the shelf; going back from it has
    // to restore the same filters the grid does.
    render(
      <MemoryRouter initialEntries={["/?type=game&platform=Xbox"]}>
        <ItemTable items={[ITEM]} />
        <Spy />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByText("Halo: Combat Evolved"));
    expect(screen.getByTestId("nav")).toHaveTextContent(
      `/items/${ITEM.id}|/?type=game&platform=Xbox`,
    );
  });
});
