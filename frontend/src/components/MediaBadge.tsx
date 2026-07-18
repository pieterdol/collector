/** Media badge in the poster's bottom-right corner: disc format for
 * physical movies (4K ULTRA HD / Blu-ray / DVD), platform abbreviation
 * for games. Styled text that evokes the real disc logos — trademarked
 * artwork is never shipped. */

import type { Item } from "../lib/types";

/** Compact 3–5 char platform label, or null when none fits the badge. */
export function platformAbbr(name: string): string | null {
  const known = PLATFORM_ABBR[name];
  if (known) return known;
  const cleaned = name.replace(/\s*\(.*\)$/, "").trim();
  if (PLATFORM_ABBR[cleaned]) return PLATFORM_ABBR[cleaned];
  if (cleaned.length <= 5) return cleaned.toUpperCase();
  const initials = cleaned
    .split(/[\s-]+/)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
  return initials.length >= 2 && initials.length <= 5 ? initials : null;
}

const PLATFORM_ABBR: Record<string, string> = {
  PlayStation: "PS1",
  "PlayStation 2": "PS2",
  "PlayStation 3": "PS3",
  "PlayStation 4": "PS4",
  "PlayStation 5": "PS5",
  "PlayStation Portable": "PSP",
  "PlayStation Vita": "VITA",
  "Xbox 360": "X360",
  "Xbox One": "XONE",
  "Xbox Series X|S": "XSX",
  "Nintendo Switch": "NSW",
  "Nintendo Switch 2": "NSW2",
  "Nintendo 64": "N64",
  "Nintendo GameCube": "NGC",
  GameCube: "NGC",
  "Wii U": "WIIU",
  "Nintendo DS": "NDS",
  "Nintendo 3DS": "3DS",
  "New Nintendo 3DS": "3DS",
  "Game Boy": "GB",
  "Game Boy Color": "GBC",
  "Game Boy Advance": "GBA",
  "PC (Microsoft Windows)": "PC",
  Windows: "PC",
  Macintosh: "MAC",
  "Sega Mega Drive/Genesis": "MD",
  "Sega Saturn": "SAT",
  "Sega Dreamcast": "DC",
  Dreamcast: "DC",
};

export function MediaBadge({ item }: { item: Item }) {
  if (item.type === "movie" && item.format === "physical") {
    const media = item.metadata.media;
    if (media === "Ultra HD Blu-ray") {
      return (
        <span className="badge badge-media badge-uhd" title="Ultra HD Blu-ray">
          <b>4K</b>
          <small>ULTRA HD</small>
        </span>
      );
    }
    if (media === "Blu-ray") {
      return (
        <span className="badge badge-media badge-bd" title="Blu-ray">
          Blu-ray
        </span>
      );
    }
    if (media === "DVD") {
      return (
        <span className="badge badge-media badge-dvd" title="DVD">
          DVD
        </span>
      );
    }
    if (media === "VHS") {
      return (
        <span className="badge badge-media" title="VHS">
          VHS
        </span>
      );
    }
    return null;
  }

  if (item.type === "game" && item.platform) {
    const abbr = platformAbbr(item.platform);
    if (!abbr) return null;
    return (
      <span className="badge badge-media" title={item.platform}>
        {abbr}
      </span>
    );
  }

  return null;
}
