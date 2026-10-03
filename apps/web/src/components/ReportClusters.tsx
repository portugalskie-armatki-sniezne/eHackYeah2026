import { useCallback, useEffect, useRef, type RefObject } from "react";
import type {
  CircleLayerSpecification,
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSource,
  MapLayerMouseEvent,
  Map as MapLibreMap,
  PointLike,
  SymbolLayerSpecification,
} from "maplibre-gl";
import type { EventPin } from "./EventMarkers";
import type { ReportCategory } from "../data/reports";

/**
 * Groups reports that sit on top of each other at the current zoom.
 *
 * Deliberately drawn as map layers rather than markers: a cluster is a tally of
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

const SOURCE = "reports";
const SHADOW_LAYER = "report-cluster-shadow";
const DISC_LAYER = "report-cluster";
const COUNT_LAYER = "report-cluster-count";

// Past this the groups break up and every report stands on its own pin.
const CLUSTER_MAX_ZOOM = 15;
// Roughly two pin heads across, so pins group once they would start to overlap.
const CLUSTER_RADIUS = 56;

const GROUPED: FilterSpecification = ["has", "point_count"];
const UNGROUPED: FilterSpecification = ["!", ["has", "point_count"]];

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
  ["step", ["get", "point_count"], 13, 5, 16, 10, 20],
  ["case", HOVERED, 2, 0],
];

// The chrome's offset block, carried onto the sheet as the disc's drawn shadow.
const SHADOW: CircleLayerSpecification = {
  id: SHADOW_LAYER,
  type: "circle",
  source: SOURCE,
  filter: GROUPED,
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
  filter: GROUPED,
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
  filter: GROUPED,
  layout: {
    "text-field": ["get", "point_count_abbreviated"],
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

/**
 * The source's payload, spelled out rather than imported: maplibre carries the
 * geojson types as a global namespace that does not resolve from this workspace,
 * and this is structurally what the source and setData accept.
 */
type ReportFeatures = {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      id: string;
      category: ReportCategory;
      reportCount: number;
    };
  }[];
};

function featureCollection(pins: EventPin[]): ReportFeatures {
  return {
    type: "FeatureCollection",
    features: pins.map((pin) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: pin.lngLat },
      properties: {
        id: pin.id,
        category: pin.category,
        reportCount: pin.reportCount,
      },
    })),
  };
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
  // what the last sync reported, so a pan that changes nothing does not tear the
  // pins down and build them again
  const lastKeyRef = useRef<string | null>(null);
  const hoveredRef = useRef<number | null>(null);

  const syncUngrouped = useCallback(() => {
    const map = mapRef.current;
    if (!map?.getSource(SOURCE)) {
      return;
    }
    const ids = new Set<string>();
    // features repeat across tile boundaries, so this collects into a set
    for (const feature of map.querySourceFeatures(SOURCE, {
      filter: UNGROUPED,
    })) {
      const id = feature.properties?.id;
      if (typeof id === "string") {
        ids.add(id);
      }
    }
    const key = [...ids].sort().join("\n");
    if (key === lastKeyRef.current) {
      return;
    }
    lastKeyRef.current = key;
    onUngroupedChange(ids);
  }, [mapRef, onUngroupedChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map) {
      return;
    }

    if (!map.getSource(SOURCE)) {
      map.addSource(SOURCE, {
        type: "geojson",
        data: featureCollection(pins),
        cluster: true,
        clusterMaxZoom: CLUSTER_MAX_ZOOM,
        clusterRadius: CLUSTER_RADIUS,
      });
      for (const layer of LAYERS) {
        map.addLayer(layer);
      }
    }

    const openCluster = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      const clusterId = feature?.properties?.cluster_id;
      if (typeof clusterId !== "number" || feature?.geometry.type !== "Point") {
        return;
      }
      const centre = feature.geometry.coordinates as [number, number];
      const source = map.getSource(SOURCE) as GeoJSONSource | undefined;
      // breaks the group open at the zoom supercluster says it splits at
      void source?.getClusterExpansionZoom(clusterId).then((zoom) => {
        map.easeTo({ center: centre, zoom, duration: 500 });
      });
    };

    const setHover = (clusterId: number | null) => {
      if (hoveredRef.current !== null) {
        map.setFeatureState(
          { source: SOURCE, id: hoveredRef.current },
          { hover: false },
        );
      }
      hoveredRef.current = clusterId;
      if (clusterId !== null) {
        map.setFeatureState({ source: SOURCE, id: clusterId }, { hover: true });
      }
    };

    const trackHover = (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.id;
      setHover(typeof id === "number" ? id : null);
    };
    const clearHover = () => setHover(null);

    const onSourceData = (event: {
      sourceId?: string;
      isSourceLoaded?: boolean;
    }) => {
      if (event.sourceId === SOURCE && event.isSourceLoaded) {
        syncUngrouped();
      }
    };

    map.on("click", DISC_LAYER, openCluster);
    map.on("mousemove", DISC_LAYER, trackHover);
    map.on("mouseleave", DISC_LAYER, clearHover);
    map.on("moveend", syncUngrouped);
    map.on("sourcedata", onSourceData);
    syncUngrouped();

    return () => {
      map.off("click", DISC_LAYER, openCluster);
      map.off("mousemove", DISC_LAYER, trackHover);
      map.off("mouseleave", DISC_LAYER, clearHover);
      map.off("moveend", syncUngrouped);
      map.off("sourcedata", onSourceData);
      hoveredRef.current = null;
      lastKeyRef.current = null;
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
    // pins are pushed through setData below, so they must not rebuild the source
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapRef, styleReady, syncUngrouped]);

  useEffect(() => {
    const source = mapRef.current?.getSource(SOURCE) as
      GeoJSONSource | undefined;
    if (!styleReady || !source) {
      return;
    }
    source.setData(featureCollection(pins));
    // setData reclusters, and the sync lands on the sourcedata it raises
  }, [mapRef, pins, styleReady]);

  return null;
}
