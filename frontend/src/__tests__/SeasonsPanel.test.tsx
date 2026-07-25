import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SeasonsPanel } from "../components/SeasonsPanel";
import type { Episode, Season } from "../lib/types";

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
    episodes_tracked: 0,
    episodes_watched: 0,
    created_at: "2026-07-21T10:00:00Z",
    updated_at: "2026-07-21T10:00:00Z",
    ...overrides,
  };
}

function episode(number: number, overrides: Partial<Episode> = {}): Episode {
  return {
    id: `e-${number}`,
    season_id: "s-1",
    episode_number: number,
    tmdb_episode_id: 63000 + number,
    name: `Episode ${number}`,
    overview: null,
    air_date: "2011-04-17",
    runtime: 55,
    watched: false,
    created_at: "2026-07-21T10:00:00Z",
    updated_at: "2026-07-21T10:00:00Z",
    ...overrides,
  };
}

/** Routes the panel's calls: season list, episode list, refresh, PATCHes. */
function mockApi(seasons: Season[], episodes: Episode[] = []) {
  const regular = seasons.filter((s) => s.season_number >= 1);
  const seasonBody = {
    seasons,
    total_seasons: regular.length,
    owned_seasons: regular.filter((s) => s.ownership === "owned").length,
    watched_seasons: regular.filter((s) => s.watched).length,
  };
  const episodeBody = {
    episodes,
    total: episodes.length,
    watched: episodes.filter((e) => e.watched).length,
  };

  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = url.includes("/episodes")
      ? method === "PATCH"
        ? episodes[0]
        : episodeBody
      : method === "PATCH"
        ? seasons[0]
        : seasonBody;
    return Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () => Promise.resolve(body),
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

/** Season rows collapse by default; the options live inside. */
async function expand(name: string) {
  fireEvent.click(await screen.findByRole("button", { name: `${name} details` }));
}

function calls(fetchMock: ReturnType<typeof mockApi>, method: string, fragment: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) => (init?.method ?? "GET") === method && String(url).includes(fragment),
  );
}

describe("SeasonsPanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders one collapsed row per season with name and episode count", async () => {
    mockApi([
      season({ season_number: 1, name: "Season 1", episode_count: 10 }),
      season({ season_number: 2, name: "Season 2", episode_count: 8 }),
    ]);
    renderPanel();

    expect(await screen.findByRole("button", { name: "Season 1 details" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Season 2 details" })).toBeInTheDocument();
    expect(screen.getByText("10 eps")).toBeInTheDocument();
    expect(screen.getByText("8 eps")).toBeInTheDocument();
    // Options only appear once a row is opened.
    expect(screen.queryByRole("combobox", { name: "Season 1 ownership" })).not.toBeInTheDocument();
  });

  it("shows derived watch progress in the header", async () => {
    mockApi([
      season({ season_number: 1, name: "Season 1", watched: true }),
      season({ season_number: 2, name: "Season 2", watched: true }),
      season({ season_number: 3, name: "Season 3" }),
    ]);
    renderPanel();

    expect(await screen.findByText("2 of 3 watched")).toBeInTheDocument();
  });

  it("shows episode progress on the collapsed row once episodes are tracked", async () => {
    mockApi([
      season({
        season_number: 1, name: "Season 1", episode_count: 10,
        episodes_tracked: 10, episodes_watched: 7,
      }),
    ]);
    renderPanel();

    expect(await screen.findByText("7 / 10")).toBeInTheDocument();
  });

  it("toggling the season checkbox PATCHes the season endpoint", async () => {
    const fetchMock = mockApi([season({ season_number: 1, name: "Season 1" })]);
    renderPanel();
    await expand("Season 1");

    fireEvent.click(screen.getByRole("checkbox", { name: "Mark Season 1 watched" }));

    await waitFor(() => {
      const [patch] = calls(fetchMock, "PATCH", `/api/items/${ID}/seasons/1`);
      expect(patch).toBeTruthy();
      expect(JSON.parse(String(patch![1]?.body))).toEqual({ watched: true });
    });
  });

  it("setting ownership to owned sends ownership in the PATCH body", async () => {
    const fetchMock = mockApi([season({ season_number: 1, name: "Season 1" })]);
    renderPanel();
    await expand("Season 1");

    fireEvent.change(screen.getByRole("combobox", { name: "Season 1 ownership" }), {
      target: { value: "owned" },
    });

    await waitFor(() => {
      const [patch] = calls(fetchMock, "PATCH", `/api/items/${ID}/seasons/1`);
      expect(JSON.parse(String(patch![1]?.body))).toEqual({ ownership: "owned" });
    });
  });

  it("shows the media select only for owned physical seasons", async () => {
    mockApi([
      season({ season_number: 1, name: "Season 1", ownership: "owned", format: "physical" }),
      season({ season_number: 2, name: "Season 2", ownership: "owned", format: "digital" }),
    ]);
    renderPanel();
    await expand("Season 1");
    await expand("Season 2");

    const media = screen.getByRole("combobox", { name: "Season 1 media" });
    const options = Array.from(media.querySelectorAll("option")).map((o) => o.textContent);
    expect(options).toContain("Blu-ray");
    expect(screen.queryByRole("combobox", { name: "Season 2 media" })).not.toBeInTheDocument();
  });

  it("shows the disc media badge on the collapsed season row", async () => {
    mockApi([
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
    const fetchMock = mockApi([
      season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627 }),
      season({ season_number: 7, name: "Season 7" }), // manual: no tmdb id
    ]);
    renderPanel();
    await expand("Season 1");
    await expand("Season 7");

    expect(screen.queryByRole("button", { name: "Remove Season 1" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove Season 7" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      const [del] = calls(fetchMock, "DELETE", `/api/items/${ID}/seasons/7`);
      expect(del).toBeTruthy();
    });
  });

  it("offers to track a season when none exist yet", async () => {
    const fetchMock = mockApi([]);
    renderPanel();

    expect(await screen.findByText("No seasons tracked yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add season" }));

    await waitFor(() => {
      expect(calls(fetchMock, "PATCH", `/api/items/${ID}/seasons/1`)).toHaveLength(1);
    });
  });
});

describe("SeasonsPanel episodes", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lists the episodes of an opened season", async () => {
    mockApi(
      [season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627, episodes_tracked: 2 })],
      [episode(1, { name: "Winter Is Coming" }), episode(2, { name: "The Kingsroad" })],
    );
    renderPanel();
    await expand("Season 1");

    expect(await screen.findByText("Winter Is Coming")).toBeInTheDocument();
    expect(screen.getByText("The Kingsroad")).toBeInTheDocument();
  });

  it("fetches episodes from TMDB the first time a linked season is opened", async () => {
    const fetchMock = mockApi(
      [season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627 })],
      [], // nothing tracked yet
    );
    renderPanel();
    await expand("Season 1");

    await waitFor(() => {
      expect(
        calls(fetchMock, "POST", `/api/items/${ID}/seasons/1/episodes/refresh`),
      ).toHaveLength(1);
    });
  });

  it("does not ask TMDB for a manually added season", async () => {
    const fetchMock = mockApi([season({ season_number: 4, name: "Season 4" })], []);
    renderPanel();
    await expand("Season 4");

    await screen.findByText(/no episode list/i);
    expect(calls(fetchMock, "POST", "/episodes/refresh")).toHaveLength(0);
  });

  it("only fetches once, even when episodes stay empty", async () => {
    const fetchMock = mockApi(
      [season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627 })],
      [],
    );
    renderPanel();
    await expand("Season 1");
    await waitFor(() => expect(calls(fetchMock, "POST", "/episodes/refresh")).toHaveLength(1));

    fireEvent.click(screen.getByRole("button", { name: "Season 1 details" })); // collapse
    await expand("Season 1"); // and open again
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(calls(fetchMock, "POST", "/episodes/refresh")).toHaveLength(1);
  });

  it("ticking an episode PATCHes the episode endpoint", async () => {
    const fetchMock = mockApi(
      [season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627, episodes_tracked: 2 })],
      [episode(1, { name: "Winter Is Coming" }), episode(2)],
    );
    renderPanel();
    await expand("Season 1");

    fireEvent.click(await screen.findByRole("checkbox", { name: "Mark S1E1 watched" }));

    await waitFor(() => {
      const [patch] = calls(fetchMock, "PATCH", `/api/items/${ID}/seasons/1/episodes/1`);
      expect(patch).toBeTruthy();
      expect(JSON.parse(String(patch![1]?.body))).toEqual({ watched: true });
    });
  });

  it("labels a watched episode's checkbox as the un-watch action", async () => {
    mockApi(
      [season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627, episodes_tracked: 1,
                episodes_watched: 1 })],
      [episode(1, { watched: true })],
    );
    renderPanel();
    await expand("Season 1");

    expect(await screen.findByRole("checkbox", { name: "Mark S1E1 unwatched" })).toBeChecked();
  });

  it("shows episode watch progress inside the season", async () => {
    mockApi(
      [season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627, episodes_tracked: 2,
                episodes_watched: 1 })],
      [episode(1, { watched: true }), episode(2)],
    );
    renderPanel();
    await expand("Season 1");

    expect(await screen.findByText("1 of 2 watched")).toBeInTheDocument();
  });

  it("re-checking with TMDB forces a refresh", async () => {
    const fetchMock = mockApi(
      [season({ season_number: 1, name: "Season 1", tmdb_season_id: 3627, episodes_tracked: 2 })],
      [episode(1), episode(2)],
    );
    renderPanel();
    await expand("Season 1");

    // The control is disabled while the list is loading.
    const button = await screen.findByRole("button", { name: "Check TMDB for new episodes" });
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => {
      const [post] = calls(fetchMock, "POST", "/episodes/refresh");
      expect(post).toBeTruthy();
      expect(String(post![0])).toContain("force=true");
    });
  });
});
