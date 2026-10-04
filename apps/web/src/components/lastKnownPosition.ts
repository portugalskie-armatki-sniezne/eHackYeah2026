const STORAGE_KEY = "lastKnownPosition";

/**
 * The place the device was last seen, kept so the map opens where the user
 * stands instead of panning there once the first fix arrives. A fix takes a
 * moment (and a permission prompt on the first visit), so on a first-ever
 * visit there is nothing stored and the map falls back to the city view.
 */
export function readLastKnownPosition(): [number, number] | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return null;
    }
    const [longitude, latitude] = JSON.parse(stored) as unknown[];
    if (
      typeof longitude === "number" &&
      typeof latitude === "number" &&
      Number.isFinite(longitude) &&
      Number.isFinite(latitude) &&
      Math.abs(longitude) <= 180 &&
      Math.abs(latitude) <= 90
    ) {
      return [longitude, latitude];
    }
  } catch {
    // unreadable or blocked storage; the city view holds
  }
  return null;
}

export function saveLastKnownPosition(lngLat: [number, number]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lngLat));
  } catch {
    // storage can be blocked; this load is unaffected
  }
}
