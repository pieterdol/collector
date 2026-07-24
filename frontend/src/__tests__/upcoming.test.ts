import { describe, expect, it } from "vitest";
import { groupByRelease, releaseInfo } from "../lib/upcoming";
import type { Item } from "../lib/types";

// Fixed reference date so countdowns are deterministic.
const TODAY = new Date(2026, 6, 24); // 24-07-2026

describe("releaseInfo", () => {
  it("formats full dates as dd-mm-yyyy with a month group", () => {
    const info = releaseInfo("2026-12-18", TODAY)!;
    expect(info.dateLabel).toBe("18-12-2026");
    expect(info.groupLabel).toBe("December 2026");
  });

  it("formats partial dates and skips the countdown chip", () => {
    expect(releaseInfo("2026-09", TODAY)).toMatchObject({
      dateLabel: "09-2026",
      groupLabel: "September 2026",
      chip: null,
      soon: false,
    });
    expect(releaseInfo("2027", TODAY)).toMatchObject({
      dateLabel: "2027",
      groupLabel: "2027",
      chip: null,
    });
  });

  it("returns null for missing or malformed values", () => {
    expect(releaseInfo(undefined, TODAY)).toBeNull();
    expect(releaseInfo("soon™", TODAY)).toBeNull();
  });

  it("counts down in days, then weeks, then months", () => {
    expect(releaseInfo("2026-07-24", TODAY)!.chip).toBe("today");
    expect(releaseInfo("2026-07-25", TODAY)!.chip).toBe("tomorrow");
    expect(releaseInfo("2026-07-29", TODAY)!.chip).toBe("in 5 days");
    expect(releaseInfo("2026-08-14", TODAY)!.chip).toBe("in 3 weeks");
    expect(releaseInfo("2026-12-18", TODAY)!.chip).toBe("in 5 months");
  });

  it("marks releases within a week as soon", () => {
    expect(releaseInfo("2026-07-31", TODAY)!.soon).toBe(true);
    expect(releaseInfo("2026-08-01", TODAY)!.soon).toBe(false);
  });
});

describe("groupByRelease", () => {
  const item = (title: string, release: string) =>
    ({ id: title, title, metadata: { release_date: release } }) as unknown as Item;

  it("groups server-sorted items under month or year headers", () => {
    const groups = groupByRelease(
      [
        item("Soon", "2026-07-27"),
        item("Next month partial", "2026-08"),
        item("Next month full", "2026-08-14"),
        item("Sometime 2027", "2027"),
      ],
      TODAY,
    );
    expect(groups.map((g) => g.label)).toEqual(["July 2026", "August 2026", "2027"]);
    expect(groups[1].rows.map((r) => r.item.title)).toEqual([
      "Next month partial",
      "Next month full",
    ]);
  });

  it("drops items whose release date cannot be parsed", () => {
    const groups = groupByRelease([item("Bad", "TBA"), item("Good", "2026-08-01")], TODAY);
    expect(groups).toHaveLength(1);
    expect(groups[0].rows[0].item.title).toBe("Good");
  });
});
