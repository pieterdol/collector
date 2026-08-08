import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SearchBox } from "../components/SearchBox";

/** Shows the live query string, so a test can assert on the URL itself. */
function CurrentSearch() {
  return <output data-testid="search">{useLocation().search}</output>;
}

/** Stands in for anything that changes the URL from outside the box —
 * back/forward, a filter link, a fresh navigation. */
function Elsewhere() {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate("/?q=elden")}>
      navigate elsewhere
    </button>
  );
}

function renderBox(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <SearchBox />
      <CurrentSearch />
      <Elsewhere />
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

describe("SearchBox typing", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("keeps a character typed just as the previous search fires", () => {
    renderBox();
    fireEvent.change(input(), { target: { value: "F" } });

    // The debounce writes ?q=F, which comes back as a params change. A
    // keystroke landing in that same flush used to be overwritten by it:
    // typing "Far Cry" produced "Fr Cry".
    act(() => {
      vi.advanceTimersByTime(250);
      fireEvent.change(input(), { target: { value: "Fa" } });
    });

    expect(input()).toHaveValue("Fa");
  });

  it("carries the whole term into the URL when typing outruns the debounce", () => {
    renderBox();
    for (const term of ["F", "Fa", "Far", "Far ", "Far C", "Far Cr", "Far Cry"]) {
      act(() => {
        vi.advanceTimersByTime(250);
        fireEvent.change(input(), { target: { value: term } });
      });
    }
    act(() => vi.advanceTimersByTime(250));

    expect(input()).toHaveValue("Far Cry");
    expect(url()).toContain("q=Far+Cry");
  });

  it("still follows the URL when something else changes it", () => {
    // Back/forward and filter links must keep working — that sync is why the
    // effect exists at all.
    renderBox("/?q=dune");
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /navigate elsewhere/i }));
    });
    expect(input()).toHaveValue("elden");
  });
});
