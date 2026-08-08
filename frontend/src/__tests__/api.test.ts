import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, NetworkError, getToken, setToken, upload } from "../lib/api";

describe("api client", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  function mockResponse(status: number, body: unknown) {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: status < 400,
      status,
      statusText: "status",
      json: () => Promise.resolve(body),
    });
  }

  it("attaches the bearer token when present", async () => {
    setToken("tok-123");
    mockResponse(200, { ok: true });
    await api("/api/items");
    const [, options] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options.headers.Authorization).toBe("Bearer tok-123");
  });

  it("serialises array params as repeated keys", async () => {
    mockResponse(200, {});
    await api("/api/items", { params: { type: ["book", "game"], q: "dune" } });
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("type=book");
    expect(String(url)).toContain("type=game");
    expect(String(url)).toContain("q=dune");
  });

  it("skips empty params", async () => {
    mockResponse(200, {});
    await api("/api/items", { params: { q: "", sort: undefined } });
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).not.toContain("q=");
    expect(String(url)).not.toContain("sort=");
  });

  it("throws ApiError with backend detail on failure", async () => {
    mockResponse(409, { detail: "already exists" });
    await expect(api("/api/auth/register", { method: "POST", body: {} })).rejects.toThrow(
      "already exists",
    );
  });

  it("clears the token on 401", async () => {
    setToken("tok-123");
    mockResponse(401, { detail: "expired" });
    await expect(api("/api/items")).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
  });

  describe("unreachable server", () => {
    // Browsers word a failed fetch unhelpfully — "Load failed" (Safari),
    // "Failed to fetch" (Chrome). Those used to reach the login form verbatim.
    function mockOffline(message: string) {
      (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new TypeError(message));
    }

    it("explains a failed request instead of repeating the browser wording", async () => {
      mockOffline("Load failed");
      await expect(api("/api/auth/login", { method: "POST", body: {} })).rejects.toThrow(
        /couldn't reach the server/i,
      );
    });

    it("throws NetworkError, keeping the browser message as the cause", async () => {
      mockOffline("Failed to fetch");
      const err = await api("/api/items").catch((e: unknown) => e);
      expect(err).toBeInstanceOf(NetworkError);
      expect(err).not.toBeInstanceOf(ApiError);
      expect((err as NetworkError).cause).toBeInstanceOf(TypeError);
    });

    it("keeps you signed in — a dropped connection is not a rejected token", async () => {
      setToken("tok-123");
      mockOffline("Load failed");
      await expect(api("/api/items")).rejects.toBeInstanceOf(NetworkError);
      expect(getToken()).toBe("tok-123");
    });

    it("covers uploads too", async () => {
      mockOffline("Load failed");
      const file = new File(["x"], "cover.jpg", { type: "image/jpeg" });
      await expect(upload("/api/items/1/cover", file)).rejects.toBeInstanceOf(NetworkError);
    });

    it("leaves non-network rejections alone", async () => {
      const abort = new DOMException("The user aborted a request.", "AbortError");
      (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(abort);
      await expect(api("/api/items")).rejects.toBe(abort);
    });
  });
});
