/** Router state that lets an item page send you back where you came from. */

import { useLocation } from "react-router-dom";

/**
 * The current list URL, filters and all, for `state` on a link into an item.
 * ItemDetail's back button reads it; without it the filters are lost, since
 * they live in the query string and the button would fall back to plain "/".
 */
export function useListOrigin(): { from: string } {
  const location = useLocation();
  return { from: location.pathname + location.search };
}
