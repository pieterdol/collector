import { describe, expect, it } from "vitest";
import { musicTracks } from "../lib/music";

describe("musicTracks", () => {
  it("reads the tracklist a provider stored on the item", () => {
    expect(
      musicTracks({
        tracks: [
          { position: "A1", title: "Everything in Its Right Place", length: "4:11" },
          { position: "A2", title: "Kid A", length: "4:44" },
        ],
      }),
    ).toEqual([
      { position: "A1", title: "Everything in Its Right Place", length: "4:11" },
      { position: "A2", title: "Kid A", length: "4:44" },
    ]);
  });

  it("keeps tracks whose length is unknown", () => {
    expect(musicTracks({ tracks: [{ position: "B1", title: "Untitled", length: null }] })).toEqual([
      { position: "B1", title: "Untitled", length: null },
    ]);
  });

  it("drops entries without a title", () => {
    const tracks = musicTracks({
      tracks: [{ position: "A1", title: "Real" }, { position: "A2" }, "nonsense", null],
    });
    expect(tracks).toEqual([{ position: "A1", title: "Real", length: null }]);
  });

  it("returns nothing for items with no tracklist", () => {
    expect(musicTracks({})).toEqual([]);
    expect(musicTracks({ tracks: "not an array" })).toEqual([]);
  });
});
