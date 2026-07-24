import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Settings from "../pages/Settings";

function mockFetch(body: object = { imported: 2, skipped: 1, total: 3 }, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok,
        status: ok ? 200 : 400,
        statusText: ok ? "OK" : "Bad Request",
        json: () => Promise.resolve(ok ? body : { detail: "That file is not valid JSON" }),
      } as Response),
    ),
  );
}

function renderSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/settings"]}>
        <Settings />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function chooseEpicFile() {
  const file = new File(["[]"], "legendary_library.json", { type: "application/json" });
  fireEvent.change(screen.getByLabelText("Epic library file"), { target: { files: [file] } });
  return file;
}

describe("Settings Epic import", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uploads the chosen library file as a job and reviews the result", async () => {
    mockJobFetch(REVIEW_JOB);
    renderSettings();
    chooseEpicFile();
    fireEvent.click(screen.getByRole("button", { name: "Import Epic library" }));

    // The upload posts multipart to the epic endpoint…
    await waitFor(() => {
      const call = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
        ([url, options]) =>
          String(url).endsWith("/api/epic/import") &&
          (options as RequestInit | undefined)?.method === "POST",
      );
      expect(call).toBeDefined();
      expect((call![1] as RequestInit).body).toBeInstanceOf(FormData);
    });
    // …and the job's review list appears.
    expect(await screen.findByText("Returnal")).toBeInTheDocument();
  });

  it("confirms the selection against the epic endpoint", async () => {
    mockJobFetch(REVIEW_JOB);
    renderSettings();
    chooseEpicFile();
    fireEvent.click(screen.getByRole("button", { name: "Import Epic library" }));

    fireEvent.click(await screen.findByRole("button", { name: "Import 2 games" }));
    await waitFor(() => {
      const call = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(([url]) =>
        String(url).includes("/api/epic/import/j1/confirm"),
      );
      expect(call).toBeDefined();
    });
  });

  it("keeps the import button disabled until a file is chosen", () => {
    mockJobFetch(REVIEW_JOB);
    renderSettings();
    expect(screen.getByRole("button", { name: "Import Epic library" })).toBeDisabled();
  });

  it("shows the server's error for a rejected file", async () => {
    mockFetch({}, false);
    renderSettings();
    chooseEpicFile();
    fireEvent.click(screen.getByRole("button", { name: "Import Epic library" }));

    expect(await screen.findByText("That file is not valid JSON")).toBeInTheDocument();
  });
});

/** PSN runs as a polled background job: POST returns a job id, GET
 * reports progress until done/error. */
function mockJobFetch(job: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const polling = /\/api\/(psn|epic|gog)\/import\/[^/]+$/.test(url);
      return Promise.resolve({
        ok: true,
        status: polling ? 200 : 202,
        statusText: "OK",
        json: () => Promise.resolve(polling ? job : { job_id: "j1" }),
      } as Response);
    }),
  );
}

function startPsnImport() {
  fireEvent.change(screen.getByLabelText("NPSSO token"), {
    target: { value: "npsso-cookie-value" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Import PlayStation library" }));
}

describe("Settings PSN import", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("starts a job with PS Plus excluded by default and shows the result", async () => {
    mockJobFetch({ status: "done", phase: "Done", done: 0, total: 5, imported: 4, skipped: 1 });
    renderSettings();
    startPsnImport();

    expect(await screen.findByText("Imported 4 games.")).toBeInTheDocument();
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url, options]) =>
        String(url).includes("/api/psn/import") &&
        (options as RequestInit | undefined)?.method === "POST",
    )!;
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      npsso: "npsso-cookie-value",
      include_ps_plus: false,
      dedupe_cross_gen: false,
    });
  });

  it("drops PS4 twins when the dedupe toggle is checked", async () => {
    mockJobFetch({ status: "done", phase: "Done", done: 0, total: 4, imported: 4, skipped: 0 });
    renderSettings();
    fireEvent.click(screen.getByLabelText("Skip PS4 versions of games you also own on PS5"));
    startPsnImport();

    await waitFor(() => {
      const call = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
        ([url, options]) =>
          String(url).includes("/api/psn/import") &&
          (options as RequestInit | undefined)?.method === "POST",
      );
      expect(call).toBeDefined();
      expect(JSON.parse(String((call![1] as RequestInit).body)).dedupe_cross_gen).toBe(true);
    });
  });

  it("includes PS Plus games when the toggle is checked", async () => {
    mockJobFetch({ status: "done", phase: "Done", done: 0, total: 5, imported: 5, skipped: 0 });
    renderSettings();
    fireEvent.click(screen.getByLabelText("Include PS Plus games"));
    startPsnImport();

    await waitFor(() => {
      const call = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
        ([url, options]) =>
          String(url).includes("/api/psn/import") &&
          (options as RequestInit | undefined)?.method === "POST",
      );
      expect(call).toBeDefined();
      expect(JSON.parse(String((call![1] as RequestInit).body)).include_ps_plus).toBe(true);
    });
  });

  it("shows the job's phase and progress while it runs", async () => {
    mockJobFetch({ status: "running", phase: "Fetching purchased games", done: 400, total: 1400 });
    renderSettings();
    startPsnImport();

    expect(await screen.findByText(/Fetching purchased games/)).toBeInTheDocument();
    expect(screen.getByText("400/1400")).toBeInTheDocument();
  });

  it("shows the job's error when it fails", async () => {
    mockJobFetch({ status: "error", phase: "Failed", done: 0, total: 0, detail: "NPSSO token was rejected" });
    renderSettings();
    startPsnImport();

    expect(await screen.findByText(/NPSSO token was rejected/)).toBeInTheDocument();
  });

  it("keeps the import button disabled until a token is entered", () => {
    mockJobFetch({});
    renderSettings();
    expect(screen.getByRole("button", { name: "Import PlayStation library" })).toBeDisabled();
  });
});

const REVIEW_JOB = {
  status: "review",
  phase: "Waiting for review",
  done: 0,
  total: 0,
  candidates: [
    { title_id: "PPSA01284", name: "Returnal", platform: "PS5", subscription: null, reason: null },
    { title_id: "CUSA00207", name: "Bloodborne", platform: "PS4", subscription: null, reason: null },
  ],
  excluded: [
    { title_id: "CUSA00119", name: "Prime Video", platform: "PS4", subscription: null, reason: "media app" },
  ],
};

describe("Settings PSN review step", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lists candidates and keeps the excluded section collapsed", async () => {
    mockJobFetch(REVIEW_JOB);
    renderSettings();
    startPsnImport();

    expect(await screen.findByText("Returnal")).toBeInTheDocument();
    expect(screen.getByText("Bloodborne")).toBeInTheDocument();
    expect(screen.queryByText("Prime Video")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Auto-excluded \(1\)/ }));
    expect(screen.getByText("Prime Video")).toBeInTheDocument();
    expect(screen.getByText("media app")).toBeInTheDocument();
  });

  it("confirms only the selected titles", async () => {
    mockJobFetch(REVIEW_JOB);
    renderSettings();
    startPsnImport();

    fireEvent.click(await screen.findByRole("checkbox", { name: /Bloodborne/ }));
    fireEvent.click(screen.getByRole("button", { name: "Import 1 game" }));

    await waitFor(() => {
      const call = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(([url]) =>
        String(url).includes("/confirm"),
      );
      expect(call).toBeDefined();
      expect(JSON.parse(String((call![1] as RequestInit).body))).toEqual({
        title_ids: ["PPSA01284"],
      });
    });
  });

  it("can rescue an auto-excluded title", async () => {
    mockJobFetch(REVIEW_JOB);
    renderSettings();
    startPsnImport();

    fireEvent.click(await screen.findByRole("button", { name: /Auto-excluded \(1\)/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Prime Video/ }));
    expect(screen.getByRole("button", { name: "Import 3 games" })).toBeInTheDocument();
  });
});

describe("Settings GOG import", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uploads the chosen library file to the gog import endpoint", async () => {
    mockJobFetch({ status: "done", phase: "Done", done: 0, total: 1, imported: 1, skipped: 0 });
    renderSettings();
    const file = new File(["{}"], "gog_library.json", { type: "application/json" });
    fireEvent.change(screen.getByLabelText("GOG library file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Import GOG library" }));

    await waitFor(() => {
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
      expect(calls.some(([url]) => String(url).includes("/api/gog/import"))).toBe(true);
    });
    expect(await screen.findByText("Imported 1 game.")).toBeInTheDocument();
  });
});

describe("Settings review notes", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps a game owned on another platform selected, with a note", async () => {
    mockJobFetch({
      status: "review",
      phase: "Waiting for review",
      done: 0,
      total: 0,
      candidates: [
        {
          title_id: "Bree",
          name: "Hogwarts Legacy",
          platform: "PC",
          subscription: null,
          reason: null,
          note: "also owned on PlayStation 5",
        },
      ],
      excluded: [],
    });
    renderSettings();
    chooseEpicFile();
    fireEvent.click(screen.getByRole("button", { name: "Import Epic library" }));

    expect(await screen.findByText("also owned on PlayStation 5")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Hogwarts Legacy/ })).toBeChecked();
    expect(screen.getByRole("button", { name: "Import 1 game" })).toBeInTheDocument();
  });
});
