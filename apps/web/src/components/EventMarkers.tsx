import { useEffect, useRef, type RefObject } from "react";
import { Marker, type Map as MapLibreMap } from "maplibre-gl";
import type { ReportCategory } from "../data/reports";
import "./EventMarkers.css";

export type EventPin = {
  id: string;
  lngLat: [number, number];
  description: string;
  image: File | null;
  imageUrl: string | null;
  /** picks the head's pictogram: "!" for a fault, "+" for an improvement */
  category: ReportCategory;
  /** how many filings the pin stands for; above one it carries a count */
  reportCount: number;
};

/** What a pin dropped on the map is until its category is chosen. */
export const DEFAULT_PIN_CATEGORY: ReportCategory = "issue";

type EventMarkersProps = {
  mapRef: RefObject<MapLibreMap | null>;
  /** Flipped on style.load, by which point the map instance exists. */
  styleReady: boolean;
  pins: EventPin[];
  /**
   * Ids of the reports to pin, when something upstream is grouping them. Null
   * while nothing is, in which case every pin is drawn.
   */
  ungroupedIds: ReadonlySet<string> | null;
  /** Where the pin being described will land; shown faint until it is added. */
  draftLngLat: [number, number] | null;
};

type PinElementOptions = {
  category: ReportCategory;
  draft?: boolean;
  imageUrl?: string | null;
  reportCount?: number;
};

const SVG_NS = "http://www.w3.org/2000/svg";

// The head's centre mark doubles as the category pictogram, drawn on the head's
// own grid around the point the plain reticle dot used to sit on: a bar and a dot
// for a fault, a cross for an improvement. Both are struck with the outline's pen.
const CATEGORY_GLYPHS: Record<ReportCategory, string> = {
  // bar, gap, dot: an "!" 11.5 units tall, so it squares off against the cross.
  // The dot is a stroke of the pen's own width rather than a filled square, so it
  // keeps step with the bar instead of fattening as the head opens.
  issue: `
    <path class="event-pin__glyph" d="M0 -33.75 V-26.25 M0 -24.75 V-22.25" />
  `,
  // arms of that same length, crossed on the centre point
  improvement: `
    <path class="event-pin__glyph" d="M-5.75 -28 H5.75 M0 -33.75 V-22.25" />
  `,
};

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
  {
    category,
    draft = false,
    imageUrl = null,
    reportCount = 1,
  }: PinElementOptions,
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
    ${CATEGORY_GLYPHS[category]}
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

  // An aggregate carries the number of filings behind it. Outside the head's
  // plates, so the figure keeps its size however far the head stretches; the
  // count is already in the marker's label, so the badge itself is not read out.
  if (reportCount > 1) {
    const count = document.createElement("span");
    count.className = "event-pin__count";
    count.setAttribute("aria-hidden", "true");
    count.textContent = String(reportCount);
    drop.append(count);
  }

  element.append(drop);
  return element;
}

function pinLabel(pin: EventPin, index: number): string {
  const kind = pin.category === "improvement" ? "Improvement" : "Fault";
  const aggregate = pin.reportCount > 1 ? `, ${pin.reportCount} reports` : "";
  return `${kind} pin ${index + 1}${aggregate}: ${pin.description}`;
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
  ungroupedIds,
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
    // A report swept into a cluster is drawn by the disc instead, so its pin comes
    // down until the zoom that breaks the group open puts it back.
    const wanted = new Set(
      pins
        .filter((pin) => !ungroupedIds || ungroupedIds.has(pin.id))
        .map((pin) => pin.id),
    );

    for (const [id, marker] of markers) {
      if (!wanted.has(id)) {
        marker.remove();
        markers.delete(id);
      }
    }

    // Numbered off the full list, so a pin keeps its label as groups come and go.
    pins.forEach((pin, index) => {
      if (!wanted.has(pin.id) || markers.has(pin.id)) {
        return;
      }
      const marker = new Marker({
        element: pinElement(pinLabel(pin, index), {
          category: pin.category,
          imageUrl: pin.imageUrl,
          reportCount: pin.reportCount,
        }),
        anchor: "bottom",
      })
        .setLngLat(pin.lngLat)
        .addTo(map);
      markers.set(pin.id, marker);
    });
  }, [mapRef, pins, styleReady, ungroupedIds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map || !draftLngLat) {
      return;
    }
    const marker = new Marker({
      element: pinElement("New pin", {
        category: DEFAULT_PIN_CATEGORY,
        draft: true,
      }),
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
