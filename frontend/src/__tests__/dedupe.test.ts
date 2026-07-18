import { describe, expect, it } from "vitest";
import { flattenItemPages } from "../lib/queries";
import type { Item } from "../lib/types";

function item(id: string, title: string) {
  return { id, title } as unknown as Item;
}

describe("flattenItemPages", () => {
  it("flattens pages in order", () => {
    const pages = [
      { items: [item("1", "A"), item("2", "B")], total: 3 },
      { items: [item("3", "C")], total: 3 },
    ];
    expect(flattenItemPages(pages).map((i) => i.id)).toEqual(["1", "2", "3"]);
  });

  it("drops items already seen on an earlier page (offset drift)", () => {
    const pages = [
      { items: [item("1", "A"), item("2", "B")], total: 4 },
      { items: [item("2", "B"), item("3", "C")], total: 4 },
    ];
    expect(flattenItemPages(pages).map((i) => i.id)).toEqual(["1", "2", "3"]);
  });

  it("handles undefined pages", () => {
    expect(flattenItemPages(undefined)).toEqual([]);
  });
});
