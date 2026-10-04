import { useSyncExternalStore } from "react";

export type Route = "map" | "about" | "initiatives";

// Every navbar link is a hash, so the page is whatever the hash names. Anything
// else, including the empty hash and the skip link's "#main", is the map.
function readRoute(): Route {
  if (window.location.hash === "#about") return "about";
  if (window.location.hash === "#initiatives") return "initiatives";
  return "map";
}

function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener);
  return () => window.removeEventListener("hashchange", listener);
}

/** The page the address bar points at; it follows the hash as it changes. */
export default function useHashRoute(): Route {
  return useSyncExternalStore(subscribe, readRoute);
}
