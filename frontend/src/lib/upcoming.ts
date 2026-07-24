/** Release-date logic for the Upcoming page. Release dates are ISO
 * strings from the providers, full ("2026-12-18") or partial ("2026-09",
 * "2027"); partial dates label and group differently and never get a
 * countdown chip. */

import type { Item } from "./types";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export interface ReleaseInfo {
  /** dd-mm-yyyy, mm-yyyy or yyyy, matching the date's precision. */
  dateLabel: string;
  /** Section header: "December 2026", or the bare year for year-only dates. */
  groupLabel: string;
  /** Countdown ("today", "in 5 days", …); null for partial dates. */
  chip: string | null;
  /** Full date within the next 7 days — rendered as an accent chip. */
  soon: boolean;
}

export function releaseInfo(release: unknown, today: Date = new Date()): ReleaseInfo | null {
  if (typeof release !== "string") return null;
  const match = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(release);
  if (!match) return null;
  const [, year, month, day] = match;

  if (!month) return { dateLabel: year, groupLabel: year, chip: null, soon: false };
  const groupLabel = `${MONTHS[Number(month) - 1]} ${year}`;
  if (!day) return { dateLabel: `${month}-${year}`, groupLabel, chip: null, soon: false };

  const date = new Date(Number(year), Number(month) - 1, Number(day));
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.max(0, Math.round((date.getTime() - start.getTime()) / 864e5));
  return {
    dateLabel: `${day}-${month}-${year}`,
    groupLabel,
    chip: countdown(days),
    soon: days <= 7,
  };
}

function countdown(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days <= 13) return `in ${days} days`;
  if (days <= 56) return `in ${Math.round(days / 7)} weeks`;
  return `in ${Math.max(2, Math.round(days / 30.4))} months`;
}

export interface ReleaseGroup {
  label: string;
  rows: Array<{ item: Item; info: ReleaseInfo }>;
}

/** Bucket server-sorted (sort=release) items under consecutive period
 * headers; items without a parseable release date are dropped. */
export function groupByRelease(items: Item[], today: Date = new Date()): ReleaseGroup[] {
  const groups: ReleaseGroup[] = [];
  for (const item of items) {
    const info = releaseInfo(item.metadata.release_date, today);
    if (!info) continue;
    const last = groups[groups.length - 1];
    if (last && last.label === info.groupLabel) last.rows.push({ item, info });
    else groups.push({ label: info.groupLabel, rows: [{ item, info }] });
  }
  return groups;
}
