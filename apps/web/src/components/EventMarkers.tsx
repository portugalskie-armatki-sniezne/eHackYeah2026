import { useEffect, useRef, type RefObject } from "react";
import { Marker, type Map as MapLibreMap } from "maplibre-gl";
import "./EventMarkers.css";

export type EventPin = {
  id: string;
  lngLat: [number, number];
  description: string;
  image: File | null;
  imageUrl: string | null;
};

type EventMarkersProps = {
  mapRef: RefObject<MapLibreMap | null>;
  /** Flipped on style.load, by which point the map instance exists. */
  styleReady: boolean;
  pins: EventPin[];
  /** Where the pin being described will land; shown faint until it is added. */
  draftLngLat: [number, number] | null;
};

// A drawn survey pin: a paper head outlined in ink, lifted off an amber block
// like the brand mark, tapering to the point it was dropped on. The origin of
// the viewBox is the tip, so the marker's bottom anchor lands on the ground.
function pinElement(label: string, draft = false): HTMLElement {
  const element = document.createElement("div");
  element.className = draft ? "event-pin event-pin--draft" : "event-pin";
  element.setAttribute("role", "img");
  element.setAttribute("aria-label", label);
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
  draftLngLat,
}: EventMarkersProps) {
  const markersRef = useRef(new globalThis.Map<string, Marker>());
  const draftRef = useRef<Marker | null>(null);

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
        element: pinElement(`Event pin ${index + 1}: ${pin.description}`),
        anchor: "bottom",
      })
        .setLngLat(pin.lngLat)
        .addTo(map);
      markers.set(pin.id, marker);
    });
  }, [mapRef, pins, styleReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map || !draftLngLat) {
      return;
    }
    const marker = new Marker({
      element: pinElement("New pin", true),
      anchor: "bottom",
    })
      .setLngLat(draftLngLat)
      .addTo(map);
    draftRef.current = marker;
    return () => {
      marker.remove();
      draftRef.current = null;
    };
  }, [draftLngLat, mapRef, styleReady]);

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
