import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, getToken, setToken } from "../lib/api";

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
});
