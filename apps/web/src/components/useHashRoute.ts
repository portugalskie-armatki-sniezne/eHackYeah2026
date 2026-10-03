import { useSyncExternalStore } from "react";

export type Route = "map" | "about";

// Every navbar link is a hash, so the page is whatever the hash names. Anything
// else, including the empty hash and the skip link's "#main", is the map.
function readRoute(): Route {
  return window.location.hash === "#about" ? "about" : "map";
}

function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener);
  return () => window.removeEventListener("hashchange", listener);
}

/** The page the address bar points at; it follows the hash as it changes. */
export default function useHashRoute(): Route {
  return useSyncExternalStore(subscribe, readRoute);
}
