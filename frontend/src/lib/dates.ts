/** App-wide date display. Every user-facing date renders through
 * formatDate, so swapping the format (or making it a user setting)
 * is a change in this one file. Current format: dd-mm-yyyy. */

export function formatDate(value: string | Date): string {
  if (typeof value === "string") {
    // Date-only strings (release/loan/acquisition dates) are reformatted
    // textually — parsing them lands on UTC midnight and shifts a day in
    // western timezones.
    const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (dateOnly) return `${dateOnly[3]}-${dateOnly[2]}-${dateOnly[1]}`;
  }
  const d = typeof value === "string" ? new Date(value) : value;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()}`;
}
