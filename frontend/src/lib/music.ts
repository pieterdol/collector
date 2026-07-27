/** Music metadata helpers.
 *
 * Tracklists arrive from MusicBrainz or Discogs and live in the item's
 * JSONB metadata, so nothing about their shape is guaranteed — parse
 * defensively and drop anything unusable rather than rendering junk. */

export interface Track {
  /** Side label where the carrier has sides ("A1"), else the running number. */
  position: string;
  title: string;
  /** "4:11", or null when the catalog doesn't know. */
  length: string | null;
}

function asText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

export function musicTracks(metadata: Record<string, unknown>): Track[] {
  const raw = metadata.tracks;
  if (!Array.isArray(raw)) return [];
  const tracks: Track[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const track = entry as Record<string, unknown>;
    const title = asText(track.title);
    if (!title) continue;
    tracks.push({
      position: asText(track.position) ?? "",
      title,
      length: asText(track.length),
    });
  }
  return tracks;
}
