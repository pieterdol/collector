/** Media badge in the poster's bottom-right corner: disc format for
 * physical movies and TV (4K ULTRA HD / Blu-ray / DVD), platform
 * abbreviation for games. Styled text that evokes the real disc logos —
 * trademarked artwork is never shipped. Clicking a badge filters the
 * library on it. */

import { useNavigate } from "react-router-dom";
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

/** The badge itself. The poster is one big <Link>, so this is a nested
 * interactive element: a span with button semantics that swallows the
 * click and deep-links into the filtered library instead. */
function FilterBadge({
  to,
  title,
  className = "",
  children,
}: {
  to: string;
  title: string;
  className?: string;
  children: React.ReactNode;
}) {
  const navigate = useNavigate();
  function go(e: React.MouseEvent | React.KeyboardEvent) {
    e.preventDefault();
    e.stopPropagation();
    navigate(to);
  }
  return (
    <span
      role="button"
      tabIndex={0}
      title={title}
      className={`badge badge-media ${className}`}
      onClick={go}
      onKeyDown={(e) => e.key === "Enter" && go(e)}
    >
      {children}
    </span>
  );
}

/** Disc-format badge for a media string; shared by item posters and the
 * season rows. `inline` un-pins it from the poster corner so it can sit in
 * a text row. Clicking deep-links into the media-filtered library. */
export function DiscBadge({
  media,
  to,
  inline = false,
}: {
  media: string;
  to: string;
  inline?: boolean;
}) {
  const chip = inline ? "badge-chip " : "";
  if (media === "Ultra HD Blu-ray") {
    return (
      <FilterBadge to={to} title="Ultra HD Blu-ray" className={`${chip}badge-uhd`}>
        <b>4K</b>
        <small>ULTRA HD</small>
      </FilterBadge>
    );
  }
  if (media === "Blu-ray") {
    return (
      <FilterBadge to={to} title="Blu-ray" className={`${chip}badge-bd`}>
        Blu-ray
      </FilterBadge>
    );
  }
  if (media === "DVD" || media === "VHS") {
    return (
      <FilterBadge to={to} title={media} className={chip + (media === "DVD" ? "badge-dvd" : "")}>
        {media}
      </FilterBadge>
    );
  }
  return null;
}

export function MediaBadge({ item }: { item: Item }) {
  if ((item.type === "movie" || item.type === "tv") && item.format === "physical") {
    const media = item.metadata.media;
    if (typeof media !== "string" || !media) return null;
    return <DiscBadge media={media} to={`/?type=${item.type}&media=${encodeURIComponent(media)}`} />;
  }

  if (item.type === "game" && item.platform) {
    const abbr = platformAbbr(item.platform);
    if (!abbr) return null;
    return (
      <FilterBadge
        to={`/?type=game&platform=${encodeURIComponent(item.platform)}`}
        title={item.platform}
      >
        {abbr}
      </FilterBadge>
    );
  }

  return null;
}
