import { useEffect, useRef, useState } from "react";

export type UserFix = {
  lngLat: [number, number];
  /** Horizontal accuracy in metres, as reported by the device. */
  accuracy: number;
};

export type LocationStatus =
  | "unsupported"
  | "locating"
  | "tracking"
  | "denied"
  | "error";

const WATCH_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 10_000,
  maximumAge: 5_000,
};

/**
 * Watches the device location for as long as the map is mounted. The watch
 * starts on mount, so the browser asks for permission as the map opens and the
 * dot is there without the user having to ask for it; a refusal just leaves the
 * map without a dot.
 */
export default function useUserPosition() {
  const [fix, setFix] = useState<UserFix | null>(null);
  const [status, setStatus] = useState<LocationStatus>(() =>
    typeof navigator !== "undefined" && "geolocation" in navigator
      ? "locating"
      : "unsupported",
  );
  const watchRef = useRef<number | null>(null);

  useEffect(() => {
    if (!("geolocation" in navigator)) {
      setStatus("unsupported");
      return;
    }

    watchRef.current = navigator.geolocation.watchPosition(
      ({ coords }) => {
        setFix({
          lngLat: [coords.longitude, coords.latitude],
          accuracy: coords.accuracy,
        });
        setStatus("tracking");
      },
      (error) => {
        setStatus(error.code === error.PERMISSION_DENIED ? "denied" : "error");
      },
      WATCH_OPTIONS,
    );

    return () => {
      if (watchRef.current !== null) {
        navigator.geolocation.clearWatch(watchRef.current);
        watchRef.current = null;
      }
    };
  }, []);

  return { fix, status };
}
