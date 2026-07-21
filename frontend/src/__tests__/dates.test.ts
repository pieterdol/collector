import { describe, expect, it } from "vitest";
import { formatDate } from "../lib/dates";

describe("formatDate", () => {
  it("formats timestamps as dd-mm-yyyy", () => {
    expect(formatDate("2026-03-05T10:00:00Z")).toBe("05-03-2026");
    expect(formatDate(new Date(2026, 11, 1))).toBe("01-12-2026");
  });

  it("formats date-only strings without timezone drift", () => {
    expect(formatDate("2019-03-22")).toBe("22-03-2019");
    expect(formatDate("1965-08-01")).toBe("01-08-1965");
  });
});
