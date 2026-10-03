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

type PinElementOptions = {
  draft?: boolean;
  imageUrl?: string | null;
};

const SVG_NS = "http://www.w3.org/2000/svg";

// One layer of the head, drawn on the head's own grid: the viewBox is exactly
// the paper rect, so stretching the element opens the drawing off a bottom edge
// that stays where the needle leaves it.
function headPlate(className: string, content: string): SVGSVGElement {
  const plate = document.createElementNS(SVG_NS, "svg");
  plate.setAttribute("class", `event-pin__plate ${className}`);
  plate.setAttribute("viewBox", "-12 -40 24 24");
  plate.setAttribute("aria-hidden", "true");
  plate.innerHTML = content;
  return plate;
}

function pinElement(
  label: string,
  { draft = false, imageUrl = null }: PinElementOptions = {},
): HTMLElement {
  const element = document.createElement("div");
  element.className = draft ? "event-pin event-pin--draft" : "event-pin";
  element.setAttribute("role", "img");
  element.setAttribute("aria-label", label);

  // maplibre writes the marker's position onto `element`, so the drop animation
  // needs a box of its own to transform.
  const drop = document.createElement("div");
  drop.className = "event-pin__drop";

  // Its own layer, under the needle: the block overhangs the head's bottom edge,
  // and the needle has to pass over that overhang, not under it.
  const blocks = headPlate(
    "event-pin__blocks",
    `<rect class="event-pin__block" x="-8" y="-36" width="24" height="24" />`,
  );

  const head = headPlate(
    "event-pin__head",
    `
    <rect class="event-pin__paper" x="-12" y="-40" width="24" height="24" />
    <rect class="event-pin__dot" x="-2.5" y="-30.5" width="5" height="5" />
  `,
  );

  if (imageUrl) {
    // only a pin with something to frame stretches on hover
    element.classList.add("event-pin--photo");
    // built as a node rather than markup: the url is user-supplied
    const photo = document.createElementNS(SVG_NS, "image");
    photo.setAttribute("class", "event-pin__photo");
    // Fills the head rect exactly. Any inset here is in viewBox units, so it
    // would widen into a paper gap as the head stretches; instead the outline,
    // drawn last and centred on this edge, laps over it.
    photo.setAttribute("x", "-12");
    photo.setAttribute("y", "-40");
    photo.setAttribute("width", "24");
    photo.setAttribute("height", "24");
    // "slice" crops to fill, like object-fit: cover
    photo.setAttribute("preserveAspectRatio", "xMidYMid slice");
    photo.setAttribute("href", imageUrl);
    head.append(photo);
  }
  // Last, and drawn open across the bottom centre, so the ink frames whatever
  // the head holds without ruling a line over the join the needle comes out of.
  head.insertAdjacentHTML(
    "beforeend",
    `<path class="event-pin__line" d="M5 -16 H12 V-40 H-12 V-16 H-5" />`,
  );

  const needle = document.createElementNS(SVG_NS, "svg");
  needle.setAttribute("class", "event-pin__needle");
  needle.setAttribute("viewBox", "-16 -40 32 40");
  needle.setAttribute("aria-hidden", "true");
  // Its paper runs well past the head's bottom edge so the two drawings cannot
  // part along a hairline; the head covers the overlap.
  needle.innerHTML = `
    <path class="event-pin__paper" d="M-5 -18 V-16 L0 0 L5 -16 V-18 Z" />
    <path class="event-pin__line" d="M-5 -16 L0 0 L5 -16" />
  `;

  // Back to front: amber block, then the needle over its overhang, then the head
  // over the needle's, since the photo now reaches the head's bottom edge.
  drop.append(blocks, needle, head);
  element.append(drop);
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
        element: pinElement(`Event pin ${index + 1}: ${pin.description}`, {
          imageUrl: pin.imageUrl,
        }),
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
      element: pinElement("New pin", { draft: true }),
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
