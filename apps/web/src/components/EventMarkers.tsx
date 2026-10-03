import { useEffect, useRef, type RefObject } from "react";
import { Marker, type Map as MapLibreMap } from "maplibre-gl";
import "./EventMarkers.css";

export type EventPin = {
  id: string;
  lngLat: [number, number];
};

type EventMarkersProps = {
  mapRef: RefObject<MapLibreMap | null>;
  /** Flipped on style.load, by which point the map instance exists. */
  styleReady: boolean;
  pins: EventPin[];
};

// A drawn survey pin: a paper head outlined in ink, lifted off an amber block
// like the brand mark, tapering to the point it was dropped on. The origin of
// the viewBox is the tip, so the marker's bottom anchor lands on the ground.
function pinElement(index: number): HTMLElement {
  const element = document.createElement("div");
  element.className = "event-pin";
  element.setAttribute("role", "img");
  element.setAttribute("aria-label", `Event pin ${index}`);
  element.innerHTML = `
    <svg class="event-pin__mark" viewBox="-16 -40 32 40" aria-hidden="true" focusable="false">
      <rect class="event-pin__block" x="-8" y="-36" width="24" height="24" />
      <path class="event-pin__line" d="M-12 -40 H12 V-16 H5 L0 0 L-5 -16 H-12 Z" />
      <rect class="event-pin__dot" x="-2.5" y="-30.5" width="5" height="5" />
    </svg>
  `;
  return element;
}

/**
 * Keeps one MapLibre marker per event pin. Renders no DOM of its own: the pins
 * live in the map's marker container so they stay nailed to the ground as the
 * camera moves.
 */
export default function EventMarkers({
  mapRef,
  styleReady,
  pins,
}: EventMarkersProps) {
  const markersRef = useRef(new globalThis.Map<string, Marker>());

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map) {
      return;
    }

    const markers = markersRef.current;
    const wanted = new Set(pins.map((pin) => pin.id));

    for (const [id, marker] of markers) {
      if (!wanted.has(id)) {
        marker.remove();
        markers.delete(id);
      }
    }

    pins.forEach((pin, index) => {
      if (markers.has(pin.id)) {
        return;
      }
      const marker = new Marker({
        element: pinElement(index + 1),
        anchor: "bottom",
      })
        .setLngLat(pin.lngLat)
        .addTo(map);
      markers.set(pin.id, marker);
    });
  }, [mapRef, pins, styleReady]);

  useEffect(() => {
    const markers = markersRef.current;
    return () => {
      for (const marker of markers.values()) {
        marker.remove();
      }
      markers.clear();
    };
  }, []);

  return null;
}
