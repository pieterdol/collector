import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { SearchBox } from "../components/SearchBox";

/** Shows the live query string, so a test can assert on the URL itself. */
function CurrentSearch() {
  return <output data-testid="search">{useLocation().search}</output>;
}

function renderBox(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <SearchBox />
      <CurrentSearch />
    </MemoryRouter>,
  );
}

const input = () => screen.getByRole<HTMLInputElement>("searchbox");
const url = () => screen.getByTestId("search").textContent;

describe("SearchBox clear button", () => {
  it("is absent while the box is empty", () => {
    renderBox();
    expect(screen.queryByRole("button", { name: /clear search/i })).toBeNull();
  });

  it("appears as soon as there is something to clear", () => {
    renderBox("/?q=dune");
    expect(screen.getByRole("button", { name: /clear search/i })).toBeInTheDocument();
  });

  it("empties the box and drops ?q= without waiting for the debounce", () => {
    renderBox("/?q=dune");
    expect(input()).toHaveValue("dune");

    fireEvent.click(screen.getByRole("button", { name: /clear search/i }));

    expect(input()).toHaveValue("");
    // No timer advance: clearing is an explicit action, not typing.
    expect(url()).not.toContain("q=");
  });

  it("keeps the other filters when clearing the term", () => {
    renderBox("/?type=music&sort=title&q=kid");
    fireEvent.click(screen.getByRole("button", { name: /clear search/i }));
    expect(url()).toContain("type=music");
    expect(url()).toContain("sort=title");
    expect(url()).not.toContain("q=");
  });

  it("returns focus to the box, so you can type the next search straight away", () => {
    renderBox("/?q=dune");
    fireEvent.click(screen.getByRole("button", { name: /clear search/i }));
    expect(input()).toHaveFocus();
  });

  it("disappears again once cleared", () => {
    renderBox("/?q=dune");
    fireEvent.click(screen.getByRole("button", { name: /clear search/i }));
    expect(screen.queryByRole("button", { name: /clear search/i })).toBeNull();
  });

  it("offers to clear a term that was only typed, not yet in the URL", () => {
    renderBox();
    fireEvent.change(input(), { target: { value: "herbert" } });
    expect(screen.getByRole("button", { name: /clear search/i })).toBeInTheDocument();
  });

  it("says it searches creators, since that is what the API does", () => {
    renderBox();
    expect(input().placeholder).toMatch(/authors|artists/i);
  });
});
