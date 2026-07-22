import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SeasonsPanel } from "../components/SeasonsPanel";
import type { Season } from "../lib/types";

const ID = "a507c1f7-56a9-4597-b462-657d69e448cb";

function season(overrides: Partial<Season>): Season {
  return {
    id: `s-${overrides.season_number}`,
    item_id: ID,
    season_number: 1,
    tmdb_season_id: null,
    name: null,
    episode_count: null,
    air_date: null,
    poster_path: null,
    ownership: null,
    format: null,
    media: null,
    watched: false,
    created_at: "2026-07-21T10:00:00Z",
    updated_at: "2026-07-21T10:00:00Z",
    ...overrides,
  };
}

function mockSeasons(seasons: Season[]) {
  const regular = seasons.filter((s) => s.season_number >= 1);
  const body = {
    seasons,
    total_seasons: regular.length,
    owned_seasons: regular.filter((s) => s.ownership === "owned").length,
    watched_seasons: regular.filter((s) => s.watched).length,
  };
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const responseBody = method === "PATCH" ? seasons[0] : body;
    return Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () => Promise.resolve(responseBody),
    } as Response);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SeasonsPanel itemId={ID} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SeasonsPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders one row per season with name and episode count", async () => {
    mockSeasons([
      season({ season_number: 1, name: "Season 1", episode_count: 10 }),
      season({ season_number: 2, name: "Season 2", episode_count: 8 }),
    ]);
    renderPanel();

    // name appears on the poster placeholder and in the caption
    expect(await screen.findAllByText("Season 1")).not.toHaveLength(0);
    expect(screen.getAllByText("Season 2")).not.toHaveLength(0);
    expect(screen.getByText("10 eps")).toBeInTheDocument();
    expect(screen.getByText("8 eps")).toBeInTheDocument();
  });

  it("shows derived watch progress in the header", async () => {
    mockSeasons([
      season({ season_number: 1, name: "Season 1", watched: true }),
      season({ season_number: 2, name: "Season 2", watched: true }),
      season({ season_number: 3, name: "Season 3" }),
    ]);
    renderPanel();

    expect(await screen.findByText("2 of 3 watched")).toBeInTheDocument();
  });

  it("toggling watched PATCHes the season endpoint", async () => {
    const fetchMock = mockSeasons([season({ season_number: 1, name: "Season 1" })]);
    renderPanel();

    fireEvent.click(await screen.findByRole("checkbox", { name: "Mark Season 1 watched" }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(patch).toBeTruthy();
      expect(String(patch![0])).toContain(`/api/items/${ID}/seasons/1`);
      expect(JSON.parse(String(patch![1]?.body))).toEqual({ watched: true });
    });
  });

  it("setting ownership to owned sends ownership in the PATCH body", async () => {
    const fetchMock = mockSeasons([season({ season_number: 1, name: "Season 1" })]);
    renderPanel();

    fireEvent.change(await screen.findByRole("combobox", { name: "Season 1 ownership" }), {
      target: { value: "owned" },
    });

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(patch).toBeTruthy();
      expect(JSON.parse(String(patch![1]?.body))).toEqual({ ownership: "owned" });
    });
  });

  it("shows the media select only for owned physical seasons", async () => {
    mockSeasons([
      season({ season_number: 1, name: "Season 1", ownership: "owned", format: "physical" }),
      season({ season_number: 2, name: "Season 2", ownership: "owned", format: "digital" }),
      season({ season_number: 3, name: "Season 3" }),
    ]);
    renderPanel();

    const media = await screen.findByRole("combobox", { name: "Season 1 media" });
    expect(media).toBeInTheDocument();
    const options = Array.from(media.querySelectorAll("option")).map((o) => o.textContent);
    expect(options).toContain("Blu-ray");
    expect(screen.queryByRole("combobox", { name: "Season 2 media" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Season 3 media" })).not.toBeInTheDocument();
  });

  it("shows the disc media badge on the season poster", async () => {
    mockSeasons([
      season({
        season_number: 1, name: "Season 1",
        ownership: "owned", format: "physical", media: "DVD",
        poster_path: "/media/seasons/x/s1.png",
      }),
    ]);
    renderPanel();

    expect(await screen.findByTitle("DVD")).toBeInTheDocument();
  });

  it("offers removal only for manually added seasons", async () => {
    const fetchMock = mockSeasons([
      season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627 }),
      season({ season_number: 7, name: "Season 7" }), // manual: no tmdb id
    ]);
    renderPanel();

    await screen.findAllByText("Season 1");
    expect(screen.queryByRole("button", { name: "Remove Season 1" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove Season 7" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      const del = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE");
      expect(del).toBeTruthy();
      expect(String(del![0])).toContain(`/api/items/${ID}/seasons/7`);
    });
  });

  it("offers to track a season when none exist yet", async () => {
    const fetchMock = mockSeasons([]);
    renderPanel();

    expect(await screen.findByText("No seasons tracked yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add season" }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(patch).toBeTruthy();
      expect(String(patch![0])).toContain(`/api/items/${ID}/seasons/1`);
    });
  });
});
