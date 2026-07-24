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
