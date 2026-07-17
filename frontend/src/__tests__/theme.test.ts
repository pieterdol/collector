import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyStoredTheme, currentTheme } from "../theme/useTheme";

describe("theme store", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: false }), // OS prefers dark
    );
  });

  it("defaults to dark when nothing stored and OS is dark", () => {
    expect(currentTheme()).toBe("dark");
  });

  it("follows the OS light preference when nothing stored", () => {
    (matchMedia as ReturnType<typeof vi.fn>).mockReturnValue({ matches: true });
    expect(currentTheme()).toBe("light");
  });

  it("stored choice wins over OS preference", () => {
    localStorage.setItem("collector.theme", "light");
    expect(currentTheme()).toBe("light");
  });

  it("applyStoredTheme stamps data-theme only when a choice exists", () => {
    applyStoredTheme();
    expect(document.documentElement.dataset.theme).toBeUndefined();
    localStorage.setItem("collector.theme", "dark");
    applyStoredTheme();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("ignores garbage in storage", () => {
    localStorage.setItem("collector.theme", "hotdog");
    expect(currentTheme()).toBe("dark");
    applyStoredTheme();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});
