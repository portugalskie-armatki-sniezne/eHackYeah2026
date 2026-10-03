import { useEffect, useRef, type RefObject } from "react";
import { Marker, type Map as MapLibreMap } from "maplibre-gl";
import type { UserFix } from "./useUserPosition";
import "./UserPosition.css";

type UserPositionProps = {
  mapRef: RefObject<MapLibreMap | null>;
  /** Flipped on style.load, so the marker lands on a live map. */
  styleReady: boolean;
  fix: UserFix | null;
};

function markerElement(): HTMLElement {
  const element = document.createElement("div");
  element.className = "user-dot";
  element.innerHTML = '<span class="user-dot__pulse"></span>';
  return element;
}

/**
 * Draws the device's own position as an amber survey dot. Renders no DOM of
 * its own: the dot is a MapLibre marker, so it stays pinned to the ground.
 */
export default function UserPosition({
  mapRef,
  styleReady,
  fix,
}: UserPositionProps) {
  const markerRef = useRef<Marker | null>(null);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map) {
      return;
    }

    if (!fix) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }

    if (markerRef.current) {
      markerRef.current.setLngLat(fix.lngLat);
    } else {
      // Marker.addTo reads the position, so it is set before the marker lands.
      markerRef.current = new Marker({ element: markerElement() })
        .setLngLat(fix.lngLat)
        .addTo(map);
    }
  }, [fix, mapRef, styleReady]);

  useEffect(
    () => () => {
      markerRef.current?.remove();
      markerRef.current = null;
    },
    [],
  );

  return null;
}
