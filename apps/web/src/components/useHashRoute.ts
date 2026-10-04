import { useSyncExternalStore } from "react";

export type Route =
  "map" | "about" | "initiatives" | "reports" | "notifications";

// Every navbar link is a hash, so the page is whatever the hash names. A case
// hangs off the map as "#map/<master id>". Anything else, including the empty
// hash and the skip link's "#main", is the map.
function hashParts(): string[] {
  return window.location.hash.replace(/^#/, "").split("/");
}

export function readRoute(): Route {
  const [name] = hashParts();
  if (name === "about") return "about";
  if (name === "initiatives") return "initiatives";
  if (name === "reports") return "reports";
  if (name === "notifications") return "notifications";
  return "map";
}

function readTarget(): string | null {
  const [, target] = hashParts();
  return target ? decodeURIComponent(target) : null;
}

function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener);
  return () => window.removeEventListener("hashchange", listener);
}

/** The page the address bar points at; it follows the hash as it changes. */
export default function useHashRoute(): Route {
  return useSyncExternalStore(subscribe, readRoute);
}

/** The case the hash singles out, for a link straight to one pin's sheet. */
export function useHashTarget(): string | null {
  return useSyncExternalStore(subscribe, readTarget);
}

/** The hash a link to one case's sheet on the map carries. */
export function caseHash(masterId: string): string {
  return `#map/${encodeURIComponent(masterId)}`;
}
