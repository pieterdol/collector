/** Photo of the cover: a local vision model reads the title, the catalog
 * confirms it, and the result lands in the normal search box. */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import AddItem from "../pages/AddItem";

const DUNE = {
  title: "Dune",
  type: "book",
  metadata: { authors: ["Frank Herbert"], year: 1965 },
  cover_url: null,
  external_id: "9780441172719",
};

function mockFetch(vision: boolean, photo: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/api/enrich/photo")
        ? photo
        : url.includes("/api/enrich/providers")
          ? {
              vision,
              providers: [
                { name: "openlibrary", type: "book", available: true },
                { name: "tmdb", type: "movie", available: true },
                { name: "tmdb", type: "tv", available: true },
                { name: "igdb", type: "game", available: true },
                { name: "musicbrainz", type: "music", available: true },
              ],
            }
          : { provider: "openlibrary", available: true, results: [DUNE] };
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve(body),
      } as Response);
    }),
  );
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AddItem />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function photoCalls(): Array<[string, RequestInit]> {
  return (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([url]) =>
    String(url).includes("/api/enrich/photo"),
  ) as Array<[string, RequestInit]>;
}

/** Pick a file in the cover-photo input. */
async function choosePhoto() {
  const input = (await screen.findByLabelText("Photo of the cover")) as HTMLInputElement;
  const file = new File(["jpeg-bytes"], "cover.jpg", { type: "image/jpeg" });
  fireEvent.change(input, { target: { files: [file] } });
}

describe("AddItem cover photo", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("offers the photo tab only when a vision model is configured", async () => {
    mockFetch(false, {});
    renderPage();
    await screen.findByRole("tab", { name: "Search" });
    expect(screen.queryByRole("tab", { name: /photo/i })).not.toBeInTheDocument();

    vi.unstubAllGlobals();
    mockFetch(true, {});
    renderPage();
    expect(await screen.findByRole("tab", { name: /photo/i })).toBeInTheDocument();
  });

  it("searches the catalog with the title it read off the cover", async () => {
    mockFetch(true, { read: ["Dune"], query: "Dune", platform: null });
    renderPage();

    fireEvent.click(await screen.findByRole("tab", { name: /photo/i }));
    await choosePhoto();

    await waitFor(() => expect(photoCalls()).toHaveLength(1));
    expect(photoCalls()[0][0]).toContain("type=book");
    expect(photoCalls()[0][1].method).toBe("POST");

    // The read title lands in the ordinary search box, and searches.
    const box = await screen.findByPlaceholderText(/Search Open Library/);
    expect(box).toHaveValue("Dune");
    // The ordinary debounced search then runs and lists the match.
    expect(await screen.findByText("Dune", { selector: "span" })).toBeInTheDocument();
  });

  it("prefills a near-miss the catalog did not recognise, so it can be fixed", async () => {
    mockFetch(true, { read: ["BLADE", "SHIFT UP"], query: null, platform: "PlayStation 5" });
    renderPage();

    fireEvent.click(await screen.findByRole("tab", { name: /photo/i }));
    await choosePhoto();

    const box = await screen.findByPlaceholderText(/Search Open Library/);
    expect(box).toHaveValue("BLADE");
    // What it saw is shown, so a wrong read is obvious rather than mysterious.
    expect(screen.getByText(/BLADE · SHIFT UP/)).toBeInTheDocument();
  });

  it("reports a model that isn't answering instead of failing silently", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/enrich/photo")) {
          return Promise.resolve({
            ok: false,
            status: 503,
            statusText: "Service Unavailable",
            json: () => Promise.resolve({ detail: "Ollama did not answer (ConnectError)" }),
          } as Response);
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: "OK",
          json: () =>
            Promise.resolve({
              vision: true,
              providers: [{ name: "openlibrary", type: "book", available: true }],
            }),
        } as Response);
      }),
    );
    renderPage();

    fireEvent.click(await screen.findByRole("tab", { name: /photo/i }));
    await choosePhoto();

    expect(await screen.findByText(/Ollama did not answer/)).toBeInTheDocument();
  });
});
