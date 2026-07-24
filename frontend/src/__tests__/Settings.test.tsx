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
  beforeEach(() => mockFetch());
  afterEach(() => vi.unstubAllGlobals());

  it("uploads the chosen library file to the epic import endpoint", async () => {
    renderSettings();
    chooseEpicFile();
    fireEvent.click(screen.getByRole("button", { name: "Import Epic library" }));

    await waitFor(() => {
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
      expect(calls.some(([url]) => String(url).includes("/api/epic/import"))).toBe(true);
    });
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(([url]) =>
      String(url).includes("/api/epic/import"),
    )!;
    expect((init as RequestInit).method).toBe("POST");
    expect((init as RequestInit).body).toBeInstanceOf(FormData);
  });

  it("summarizes the import result", async () => {
    renderSettings();
    chooseEpicFile();
    fireEvent.click(screen.getByRole("button", { name: "Import Epic library" }));

    expect(await screen.findByText("Imported 2 games.")).toBeInTheDocument();
    expect(screen.getByText(/1 already on your shelf/)).toBeInTheDocument();
  });

  it("keeps the import button disabled until a file is chosen", () => {
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
function mockPsnFetch(job: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const polling = url.includes("/api/psn/import/");
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
    mockPsnFetch({ status: "done", phase: "Done", done: 0, total: 5, imported: 4, skipped: 1 });
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
    mockPsnFetch({ status: "done", phase: "Done", done: 0, total: 4, imported: 4, skipped: 0 });
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
    mockPsnFetch({ status: "done", phase: "Done", done: 0, total: 5, imported: 5, skipped: 0 });
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
    mockPsnFetch({ status: "running", phase: "Fetching purchased games", done: 400, total: 1400 });
    renderSettings();
    startPsnImport();

    expect(await screen.findByText(/Fetching purchased games/)).toBeInTheDocument();
    expect(screen.getByText("400/1400")).toBeInTheDocument();
  });

  it("shows the job's error when it fails", async () => {
    mockPsnFetch({ status: "error", phase: "Failed", done: 0, total: 0, detail: "NPSSO token was rejected" });
    renderSettings();
    startPsnImport();

    expect(await screen.findByText(/NPSSO token was rejected/)).toBeInTheDocument();
  });

  it("keeps the import button disabled until a token is entered", () => {
    mockPsnFetch({});
    renderSettings();
    expect(screen.getByRole("button", { name: "Import PlayStation library" })).toBeDisabled();
  });
});

describe("Settings GOG import", () => {
  beforeEach(() => mockFetch({ imported: 1, skipped: 0, total: 1 }));
  afterEach(() => vi.unstubAllGlobals());

  it("uploads the chosen library file to the gog import endpoint", async () => {
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
