import { useCallback, useEffect, useRef, type RefObject } from "react";
import type {
  CircleLayerSpecification,
  ExpressionSpecification,
  GeoJSONSource,
  MapLayerMouseEvent,
  Map as MapLibreMap,
  PointLike,
  SymbolLayerSpecification,
} from "maplibre-gl";
import type { EventPin } from "./EventMarkers";

/**
 * Groups reports whose pins would collide in the current view.
 *
 * The grouping is done here, in screen space, rather than by the source's own
 * clustering. Supercluster builds its groups once per whole zoom level and serves
 * the floored one in between, so a radius that is 32px at zoom 14 has grown to
 * 60px by zoom 14.9; it also walks the points greedily in data order, and measures
 * groups centroid to centroid rather than pin to pin. Projecting the pins on every
 * frame the camera changes makes a group mean one thing at every zoom: the boxes
 * of these pins overlap, and every pin that overlaps one of them is in too.
 *
 * Deliberately drawn as map layers rather than markers: a group is a tally of
 * several reports, and a pin is one report. Were a group drawn as a pin it would
 * claim a place and a category that no single report filed, so groups get a shape
 * of their own - a disc with a number - and only ungrouped reports keep a pin.
 * The pins for grouped reports are taken down; see `onUngroupedChange`.
 */

// From the scaffolding palette in Map.tsx, kept local so neither module has to
// import the other.
const INK = "#141414";
const PAPER_BRIGHT = "#f8f3e6";
const AMBER = "#efb33f";

const SOURCE = "report-groups";
const SHADOW_LAYER = "report-cluster-shadow";
const DISC_LAYER = "report-cluster";
const COUNT_LAYER = "report-cluster-count";

// The box of .event-pin, which maplibre anchors at its bottom centre: two pins
// collide when their tips are closer than this on both axes.
const PIN_WIDTH = 32;
const PIN_HEIGHT = 40;

// The custom cursor replaces the system one, so a pointer change would go unseen;
// the disc answers the pointer itself instead.
const HOVERED: ExpressionSpecification = [
  "boolean",
  ["feature-state", "hover"],
  false,
];

// Grows with the size of the group, but gently: the disc is a tally, not a heat map.
const DISC_RADIUS: ExpressionSpecification = [
  "+",
  ["step", ["get", "count"], 13, 5, 16, 10, 20],
  ["case", HOVERED, 2, 0],
];

// The chrome's offset block, carried onto the sheet as the disc's drawn shadow.
const SHADOW: CircleLayerSpecification = {
  id: SHADOW_LAYER,
  type: "circle",
  source: SOURCE,
  paint: {
    "circle-color": AMBER,
    "circle-radius": DISC_RADIUS,
    "circle-translate": [3, 3],
    "circle-translate-anchor": "viewport",
  },
};

const DISC: CircleLayerSpecification = {
  id: DISC_LAYER,
  type: "circle",
  source: SOURCE,
  paint: {
    "circle-color": PAPER_BRIGHT,
    "circle-radius": DISC_RADIUS,
    "circle-stroke-color": INK,
    "circle-stroke-width": 2.5,
  },
};

const COUNT: SymbolLayerSpecification = {
  id: COUNT_LAYER,
  type: "symbol",
  source: SOURCE,
  layout: {
    "text-field": ["get", "label"],
    "text-font": ["Noto Sans Bold"],
    "text-size": 13,
    // the tally has to stay legible where discs crowd together
    "text-allow-overlap": true,
    "text-ignore-placement": true,
  },
  paint: { "text-color": INK },
};

const LAYERS = [SHADOW, DISC, COUNT];

/** True when the point is on a group, which opens rather than starting a report. */
export function isClusterAt(map: MapLibreMap, point: PointLike): boolean {
  if (!map.getLayer(DISC_LAYER)) {
    return false;
  }
  return map.queryRenderedFeatures(point, { layers: [DISC_LAYER] }).length > 0;
}

type Projected = { pin: EventPin; x: number; y: number };

type Group = {
  /**
   * A hash of the membership, so a group that survives a resync keeps its id and
   * with it its hover state. Numeric because that is what feature-state keys on.
   */
  id: number;
  /** the mean of the members' positions, where the disc is drawn */
  centre: [number, number];
  members: EventPin[];
};

function project(map: MapLibreMap, pins: EventPin[]): Projected[] {
  return pins.map((pin) => {
    const { x, y } = map.project(pin.lngLat);
    return { pin, x, y };
  });
}

/**
 * The connected components of the overlap graph: a pin's group is every pin it
 * can reach through a chain of overlapping ones. Order-independent, unlike a
 * greedy walk, and monotone in zoom: zooming in only ever splits a group.
 */
function components(points: Projected[]): Projected[][] {
  const parent = points.map((_, i) => i);
  const find = (i: number): number => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]];
      i = parent[i];
    }
    return i;
  };

  // swept left to right, so the inner loop stops at the first pin too far along
  // the x axis to overlap, instead of comparing every pair
  const order = points.map((_, i) => i).sort((a, b) => points[a].x - points[b].x);
  for (let a = 0; a < order.length; a++) {
    const i = order[a];
    for (let b = a + 1; b < order.length; b++) {
      const j = order[b];
      if (points[j].x - points[i].x >= PIN_WIDTH) {
        break;
      }
      if (Math.abs(points[j].y - points[i].y) < PIN_HEIGHT) {
        parent[find(i)] = find(j);
      }
    }
  }

  const byRoot = new Map<number, Projected[]>();
  points.forEach((point, i) => {
    const root = find(i);
    const list = byRoot.get(root);
    if (list) {
      list.push(point);
    } else {
      byRoot.set(root, [point]);
    }
  });
  return [...byRoot.values()];
}

// FNV-1a over the member ids, which are sorted first so the hash is a function of
// the membership alone. Folded to a non-negative 31-bit int.
function groupId(members: EventPin[]): number {
  let hash = 0x811c9dc5;
  for (const pin of members) {
    for (let i = 0; i < pin.id.length; i++) {
      hash ^= pin.id.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193);
    }
    // a separator, so "ab"+"c" and "a"+"bc" do not collide
    hash ^= 0x1f;
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 1;
}

function groupPins(map: MapLibreMap, pins: EventPin[]): Group[] {
  const groups: Group[] = [];
  for (const component of components(project(map, pins))) {
    if (component.length < 2) {
      continue;
    }
    const members = component
      .map((point) => point.pin)
      .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    let lng = 0;
    let lat = 0;
    for (const pin of members) {
      lng += pin.lngLat[0];
      lat += pin.lngLat[1];
    }
    groups.push({
      id: groupId(members),
      centre: [lng / members.length, lat / members.length],
      members,
    });
  }
  return groups;
}

/**
 * The first zoom at which the group comes apart, found by scaling the members'
 * screen positions the way a zoom would and regrouping. Stepped in quarters so
 * the ease lands just past the break rather than on it; members on the very
 * same spot never part, and send the camera to the map's limit.
 */
function splitZoom(map: MapLibreMap, group: Group): number {
  const zoom = map.getZoom();
  const max = map.getMaxZoom();
  const points = project(map, group.members);
  for (let step = 0.25; zoom + step < max; step += 0.25) {
    const scale = 2 ** step;
    const scaled = points.map((point) => ({
      ...point,
      x: point.x * scale,
      y: point.y * scale,
    }));
    if (components(scaled).length > 1) {
      return zoom + step;
    }
  }
  return max;
}

/**
 * The source's payload, spelled out rather than imported: maplibre carries the
 * geojson types as a global namespace that does not resolve from this workspace,
 * and this is structurally what the source and setData accept.
 */
type GroupFeatures = {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    id: number;
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      count: number;
      label: string;
    };
  }[];
};

function featureCollection(groups: Group[]): GroupFeatures {
  return {
    type: "FeatureCollection",
    features: groups.map((group) => ({
      type: "Feature",
      id: group.id,
      geometry: { type: "Point", coordinates: group.centre },
      properties: {
        count: group.members.length,
        label:
          group.members.length >= 1000
            ? `${Math.floor(group.members.length / 1000)}k`
            : String(group.members.length),
      },
    })),
  };
}

/** The membership as a whole, which is all a frame needs to know changed. */
function signature(groups: Group[]): string {
  return groups
    .map((group) => group.id)
    .sort((a, b) => a - b)
    .join(",");
}

type ReportClustersProps = {
  mapRef: RefObject<MapLibreMap | null>;
  /** Flipped on style.load, by which point the map instance exists. */
  styleReady: boolean;
  pins: EventPin[];
  /** Ids of the reports no group swallowed, which are the ones that keep a pin. */
  onUngroupedChange: (ids: ReadonlySet<string>) => void;
};

export default function ReportClusters({
  mapRef,
  styleReady,
  pins,
  onUngroupedChange,
}: ReportClustersProps) {
  // Read by the frame handler, which is bound once; the effect below keeps it
  // current and marks the grouping stale.
  const pinsRef = useRef(pins);
  const staleRef = useRef(false);
  // the camera the last grouping was made for: a pan moves every pin by the same
  // amount, so only zoom, bearing and pitch can change what overlaps
  const viewRef = useRef<string | null>(null);
  const signatureRef = useRef<string | null>(null);
  const groupsRef = useRef<Group[]>([]);
  // The pin set that goes with the discs the source is still loading. Released on
  // the frame the discs are drawn, so a pin comes down as its disc appears rather
  // than the frames before, and comes back as its disc goes rather than after.
  const pendingRef = useRef<ReadonlySet<string> | null>(null);
  const hoveredRef = useRef<number | null>(null);

  const sync = useCallback(() => {
    const map = mapRef.current;
    const source = map?.getSource(SOURCE) as GeoJSONSource | undefined;
    if (!map || !source) {
      return;
    }
    if (pendingRef.current && map.isSourceLoaded(SOURCE)) {
      onUngroupedChange(pendingRef.current);
      pendingRef.current = null;
    }
    const view = `${map.getZoom()}/${map.getBearing()}/${map.getPitch()}`;
    if (view === viewRef.current && !staleRef.current) {
      return;
    }
    viewRef.current = view;
    staleRef.current = false;

    const groups = groupPins(map, pinsRef.current);
    const membership = signature(groups);
    if (membership === signatureRef.current) {
      return;
    }
    signatureRef.current = membership;
    groupsRef.current = groups;
    source.setData(featureCollection(groups));

    const grouped = new Set<string>();
    for (const group of groups) {
      for (const pin of group.members) {
        grouped.add(pin.id);
      }
    }
    const ungrouped = new Set<string>();
    for (const pin of pinsRef.current) {
      if (!grouped.has(pin.id)) {
        ungrouped.add(pin.id);
      }
    }
    pendingRef.current = ungrouped;
  }, [mapRef, onUngroupedChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map) {
      return;
    }

    if (!map.getSource(SOURCE)) {
      map.addSource(SOURCE, {
        type: "geojson",
        data: featureCollection([]),
      });
      for (const layer of LAYERS) {
        map.addLayer(layer);
      }
    }

    const openGroup = (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.id;
      const group = groupsRef.current.find((candidate) => candidate.id === id);
      if (!group) {
        return;
      }
      map.easeTo({
        center: group.centre,
        zoom: splitZoom(map, group),
        duration: 500,
      });
    };

    const setHover = (groupId: number | null) => {
      if (hoveredRef.current !== null) {
        map.setFeatureState(
          { source: SOURCE, id: hoveredRef.current },
          { hover: false },
        );
      }
      hoveredRef.current = groupId;
      if (groupId !== null) {
        map.setFeatureState({ source: SOURCE, id: groupId }, { hover: true });
      }
    };

    const trackHover = (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.id;
      setHover(typeof id === "number" ? id : null);
    };
    const clearHover = () => setHover(null);

    map.on("click", DISC_LAYER, openGroup);
    map.on("mousemove", DISC_LAYER, trackHover);
    map.on("mouseleave", DISC_LAYER, clearHover);
    // Runs with the frame rather than at the end of a gesture, so a group forms
    // on the frame its pins meet. The work is a projection of the pins and a
    // sweep, and only when the camera has zoomed, turned or tilted since last time.
    map.on("render", sync);
    sync();

    return () => {
      map.off("click", DISC_LAYER, openGroup);
      map.off("mousemove", DISC_LAYER, trackHover);
      map.off("mouseleave", DISC_LAYER, clearHover);
      map.off("render", sync);
      hoveredRef.current = null;
      viewRef.current = null;
      signatureRef.current = null;
      groupsRef.current = [];
      pendingRef.current = null;
      try {
        for (const layer of LAYERS) {
          if (map.getLayer(layer.id)) {
            map.removeLayer(layer.id);
          }
        }
        if (map.getSource(SOURCE)) {
          map.removeSource(SOURCE);
        }
      } catch {
        // React tears a parent's effect down before its children's, so Map may
        // already have removed the map out from under this one
      }
    };
  }, [mapRef, styleReady, sync]);

  useEffect(() => {
    pinsRef.current = pins;
    staleRef.current = true;
    // a render only comes when something moves, so an idle map is regrouped by
    // hand; setData then repaints, and the pins follow on that frame
    sync();
  }, [pins, sync]);

  return null;
}
