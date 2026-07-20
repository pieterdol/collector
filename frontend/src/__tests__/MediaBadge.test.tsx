import { render as rtlRender, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { MediaBadge, platformAbbr } from "../components/MediaBadge";
import type { Item } from "../lib/types";

function render(ui: React.ReactElement) {
  return rtlRender(ui, { wrapper: MemoryRouter });
}

const base: Item = {
  id: "11111111-1111-1111-1111-111111111111",
  user_id: "u",
  type: "movie",
  format: "physical",
  status: "backlog",
  title: "Dune",
  cover_path: null,
  platform: null,
  metadata: {},
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
};

function movie(media?: string, format: Item["format"] = "physical"): Item {
  return { ...base, format, metadata: media ? { media } : {} };
}

function game(platform: string | null): Item {
  return { ...base, type: "game", platform, metadata: {} };
}

describe("MediaBadge — movies", () => {
  it("shows the yellow 4K ULTRA HD badge for Ultra HD Blu-ray", () => {
    render(<MediaBadge item={movie("Ultra HD Blu-ray")} />);
    const badge = screen.getByTitle("Ultra HD Blu-ray");
    expect(badge).toHaveTextContent("4K");
    expect(badge).toHaveTextContent("ULTRA HD");
  });

  it("shows the Blu-ray badge", () => {
    render(<MediaBadge item={movie("Blu-ray")} />);
    expect(screen.getByTitle("Blu-ray")).toHaveTextContent("Blu-ray");
  });

  it("shows the DVD badge", () => {
    render(<MediaBadge item={movie("DVD")} />);
    expect(screen.getByTitle("DVD")).toHaveTextContent("DVD");
  });

  it("shows a plain VHS badge", () => {
    render(<MediaBadge item={movie("VHS")} />);
    expect(screen.getByTitle("VHS")).toHaveTextContent("VHS");
  });

  it("renders nothing when no media is stored", () => {
    const { container } = render(<MediaBadge item={movie(undefined)} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing for digital movies even if media is set", () => {
    const { container } = render(<MediaBadge item={movie("DVD", "digital")} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("MediaBadge — tv", () => {
  function tv(media?: string, format: Item["format"] = "physical"): Item {
    return { ...base, type: "tv", format, metadata: media ? { media } : {} };
  }

  it("shows the disc badge for physical TV box sets", () => {
    render(<MediaBadge item={tv("Blu-ray")} />);
    expect(screen.getByTitle("Blu-ray")).toHaveTextContent("Blu-ray");
  });

  it("renders nothing for digital TV", () => {
    const { container } = render(<MediaBadge item={tv("DVD", "digital")} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("MediaBadge — games", () => {
  it("shows the abbreviated platform", () => {
    render(<MediaBadge item={game("PlayStation 5")} />);
    expect(screen.getByTitle("PlayStation 5")).toHaveTextContent("PS5");
  });

  it("renders nothing without a platform", () => {
    const { container } = render(<MediaBadge item={game(null)} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the platform can't be abbreviated", () => {
    const { container } = render(<MediaBadge item={game("Intellivision")} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("MediaBadge — other types", () => {
  it("renders nothing for books", () => {
    const { container } = render(<MediaBadge item={{ ...base, type: "book" }} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("platformAbbr", () => {
  it("maps common platforms", () => {
    expect(platformAbbr("PlayStation 5")).toBe("PS5");
    expect(platformAbbr("Xbox Series X|S")).toBe("XSX");
    expect(platformAbbr("Nintendo Switch")).toBe("NSW");
    expect(platformAbbr("PC (Microsoft Windows)")).toBe("PC");
    expect(platformAbbr("Wii U")).toBe("WIIU");
  });

  it("keeps short names as-is, uppercased", () => {
    expect(platformAbbr("Wii")).toBe("WII");
    expect(platformAbbr("Steam")).toBe("STEAM");
  });

  it("falls back to word initials for long multi-word names", () => {
    expect(platformAbbr("Nintendo Entertainment System")).toBe("NES");
    expect(platformAbbr("Super Nintendo Entertainment System")).toBe("SNES");
  });

  it("returns null for long single-word names", () => {
    expect(platformAbbr("Intellivision")).toBeNull();
  });
});
