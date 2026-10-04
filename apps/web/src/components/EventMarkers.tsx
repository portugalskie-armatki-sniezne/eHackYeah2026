import { useEffect, useEffectEvent, useRef, type RefObject } from "react";
import { Marker, type Map as MapLibreMap } from "maplibre-gl";
import type {
  MasterReportStatusName,
  ReportCategoryName,
} from "../api/reports";
import { useMessages } from "../i18n/locale";
import type { Messages } from "../i18n/messages";
import { STATUS_GLYPHS } from "./statusGlyphs";
import "./EventMarkers.css";

export type EventPin = {
  id: string;
  lngLat: [number, number];
  description: string;
  image: File | null;
  imageUrl: string | null;
  /** names the pin in its label: a fault or an improvement */
  category: ReportCategoryName;
  /**
   * Picks the head's pictogram and colour, the same ones the status badge
   * shows; null when the master's status is not one the interface knows.
   */
  status: MasterReportStatusName | null;
  /** how many filings the pin stands for; above one it carries a count */
  reportCount: number;
};

/** What a pin dropped on the map is until its category is chosen. */
export const DEFAULT_PIN_CATEGORY: ReportCategoryName = "issue";

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
  /** Called with the pin's id when it is clicked or picked with the keyboard. */
  onPinClick?: (id: string) => void;
};

type PinElementOptions = {
  status?: MasterReportStatusName | null;
  /** the status in words, shown on hover the way the badge spells it out */
  title?: string;
  draft?: boolean;
  imageUrl?: string | null;
  reportCount?: number;
  /** makes the pin a button that opens its sheet; a draft pin has none */
  onOpen?: () => void;
};

const SVG_NS = "http://www.w3.org/2000/svg";

// The head's centre mark is the status pictogram the reports page's badge
// shows, struck with the outline's pen. The badge draws it on a 16-unit grid
// with its centre at (8, 8); shifted by (-8, -36) that centre lands on the
// head's own, (0, -28), with four units of paper around it on every side.
function statusGlyph(status: MasterReportStatusName | null): string {
  if (!status) return "";
  return `
    <g class="event-pin__glyph" transform="translate(-8 -36)">
      ${STATUS_GLYPHS[status]}
    </g>
  `;
}

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
    status = null,
    title,
    draft = false,
    imageUrl = null,
    reportCount = 1,
    onOpen,
  }: PinElementOptions,
): HTMLElement {
  const element = document.createElement("div");
  element.className = draft ? "event-pin event-pin--draft" : "event-pin";
  // the paper takes the badge's colour for the status: amber while the work is
  // on, green once it is done
  if (status) element.classList.add(`event-pin--${status}`);
  element.setAttribute("aria-label", label);
  if (title) element.title = title;
  if (onOpen) {
    // the map's own click handler steps aside for marker elements, so the pin
    // answers the pointer itself and is reachable from the keyboard too
    element.setAttribute("role", "button");
    element.tabIndex = 0;
    element.addEventListener("click", (event) => {
      event.stopPropagation();
      onOpen();
    });
    element.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onOpen();
      }
    });
  } else {
    element.setAttribute("role", "img");
  }

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
    ${statusGlyph(status)}
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

// whether two versions of a pin draw the same marker; the element is built once,
// so a change in any of these means building it again
function sameMarker(a: EventPin, b: EventPin): boolean {
  return (
    a.description === b.description &&
    a.imageUrl === b.imageUrl &&
    a.category === b.category &&
    a.status === b.status &&
    a.reportCount === b.reportCount &&
    a.lngLat[0] === b.lngLat[0] &&
    a.lngLat[1] === b.lngLat[1]
  );
}

// the status in the interface language, as the badge spells it; null when the
// name is not one it knows, and the label leaves it out
function statusTitle(pin: EventPin, t: Messages): string | null {
  return pin.status ? t.status[pin.status] : null;
}

function pinLabel(pin: EventPin, index: number, t: Messages): string {
  return t.map.pinLabel(
    pin.category,
    index + 1,
    statusTitle(pin, t),
    pin.reportCount,
    pin.description,
  );
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
  onPinClick,
}: EventMarkersProps) {
  const markersRef = useRef(
    new globalThis.Map<string, { marker: Marker; pin: EventPin }>(),
  );
  const draftRef = useRef<Marker | null>(null);
  const t = useMessages();
  // read through an event so a new handler does not rebuild every marker
  const openPin = useEffectEvent((id: string) => onPinClick?.(id));

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

    const current = new globalThis.Map(pins.map((pin) => [pin.id, pin]));
    // A marker also comes down when its pin changed, say because another filing
    // joined its master and the count went up, and is built afresh below.
    for (const [id, entry] of markers) {
      const pin = current.get(id);
      if (!wanted.has(id) || !pin || !sameMarker(entry.pin, pin)) {
        entry.marker.remove();
        markers.delete(id);
      } else {
        // a kept marker follows the interface language without being rebuilt
        const element = entry.marker.getElement();
        element.setAttribute("aria-label", pinLabel(pin, pins.indexOf(pin), t));
        element.title = statusTitle(pin, t) ?? "";
      }
    }

    // Numbered off the full list, so a pin keeps its label as groups come and go.
    pins.forEach((pin, index) => {
      if (!wanted.has(pin.id) || markers.has(pin.id)) {
        return;
      }
      const marker = new Marker({
        element: pinElement(pinLabel(pin, index, t), {
          status: pin.status,
          title: statusTitle(pin, t) ?? undefined,
          imageUrl: pin.imageUrl,
          reportCount: pin.reportCount,
          onOpen: () => openPin(pin.id),
        }),
        anchor: "bottom",
      })
        .setLngLat(pin.lngLat)
        .addTo(map);
      markers.set(pin.id, { marker, pin });
    });
  }, [mapRef, pins, styleReady, ungroupedIds, t]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map || !draftLngLat) {
      return;
    }
    const marker = new Marker({
      element: pinElement(t.map.newPin, { draft: true }),
      anchor: "bottom",
    })
      .setLngLat(draftLngLat)
      .addTo(map);
    draftRef.current = marker;
    return () => {
      marker.remove();
      draftRef.current = null;
    };
  }, [draftLngLat, mapRef, styleReady, t.map.newPin]);

  useEffect(() => {
    const markers = markersRef.current;
    return () => {
      for (const entry of markers.values()) {
        entry.marker.remove();
      }
      markers.clear();
    };
  }, []);

  return null;
}
