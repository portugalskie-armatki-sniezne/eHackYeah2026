import { useEffect, useRef, type RefObject } from "react";
import {
  Marker,
  type GeoJSONSource,
  type Map as MapLibreMap,
} from "maplibre-gl";
import type { UserFix } from "./useUserPosition";
import "./UserPosition.css";

type UserPositionProps = {
  mapRef: RefObject<MapLibreMap | null>;
  /** Flipped on style.load, so the layers are added to a live style. */
  styleReady: boolean;
  fix: UserFix | null;
};

const SOURCE = "user-position";
const ACCURACY_FILL = "user-position-accuracy";
const ACCURACY_LINE = "user-position-accuracy-line";

// @types/geojson is only a transitive dependency of maplibre-gl and isn't
// resolvable here, so the two shapes this layer needs are spelled out.
type PolygonCollection = {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    properties: Record<string, never>;
    geometry: { type: "Polygon"; coordinates: [number, number][][] };
  }[];
};

const EMPTY: PolygonCollection = {
  type: "FeatureCollection",
  features: [],
};

const EARTH_RADIUS = 6_378_137;
const CIRCLE_STEPS = 64;

// The accuracy ring is a real-world radius, so it is drawn as a geodesic polygon
// rather than a pixel-radius circle: it then scales and tilts with the camera.
function accuracyRing(
  [lng, lat]: [number, number],
  radiusMeters: number,
): PolygonCollection {
  const latitudeSpan = (radiusMeters / EARTH_RADIUS) * (180 / Math.PI);
  const longitudeSpan =
    latitudeSpan / Math.max(Math.cos((lat * Math.PI) / 180), 1e-6);
  const ring: [number, number][] = [];
  for (let step = 0; step <= CIRCLE_STEPS; step += 1) {
    const angle = (step / CIRCLE_STEPS) * 2 * Math.PI;
    ring.push([
      lng + longitudeSpan * Math.cos(angle),
      lat + latitudeSpan * Math.sin(angle),
    ]);
  }
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: { type: "Polygon", coordinates: [ring] },
      },
    ],
  };
}

// Under the labels, so street names stay readable through the ring.
function firstSymbolLayerId(map: MapLibreMap): string | undefined {
  return map.getStyle().layers?.find((layer) => layer.type === "symbol")?.id;
}

function markerElement(): HTMLElement {
  const element = document.createElement("div");
  element.className = "user-dot";
  element.innerHTML = '<span class="user-dot__pulse"></span>';
  return element;
}

/**
 * Draws the device's own position: an amber survey dot with the reported
 * accuracy hatched around it. Renders no DOM of its own: the dot is a MapLibre
 * marker and the ring is a style layer, so both stay pinned to the ground.
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

    if (!map.getSource(SOURCE)) {
      map.addSource(SOURCE, { type: "geojson", data: EMPTY });
    }
    const before = firstSymbolLayerId(map);
    if (!map.getLayer(ACCURACY_FILL)) {
      map.addLayer(
        {
          id: ACCURACY_FILL,
          type: "fill",
          source: SOURCE,
          paint: { "fill-color": "#efb33f", "fill-opacity": 0.18 },
        },
        before,
      );
    }
    if (!map.getLayer(ACCURACY_LINE)) {
      map.addLayer(
        {
          id: ACCURACY_LINE,
          type: "line",
          source: SOURCE,
          paint: {
            "line-color": "#141414",
            "line-width": 1.5,
            "line-opacity": 0.5,
            "line-dasharray": [3, 2],
          },
        },
        before,
      );
    }

    return () => {
      // The style itself is gone after a setStyle, so removal is best-effort.
      for (const layer of [ACCURACY_LINE, ACCURACY_FILL]) {
        if (map.getLayer(layer)) {
          map.removeLayer(layer);
        }
      }
      if (map.getSource(SOURCE)) {
        map.removeSource(SOURCE);
      }
    };
  }, [mapRef, styleReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map) {
      return;
    }

    const source = map.getSource(SOURCE) as GeoJSONSource | undefined;
    if (!fix) {
      source?.setData(EMPTY);
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }

    source?.setData(accuracyRing(fix.lngLat, fix.accuracy));
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
