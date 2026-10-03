import { useCallback, useEffect, useRef, useState } from "react";
import { Map as MapLibreMap, Marker, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import MapToolbar, { type BasemapId } from "./MapToolbar";
import "./Map.css";

const KRAKOW: [number, number] = [19.945, 50.0647];
const ZOOM = 12.5;
const MARKER_COLOR = "#ed716d";

const BASEMAP_STYLES: Record<BasemapId, string> = {
  streets: "https://tiles.openfreemap.org/styles/bright",
};

export default function Map() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const map = new MapLibreMap({
      container,
      style: BASEMAP_STYLES.streets,
      center: KRAKOW,
      zoom: ZOOM,
      attributionControl: false,
    });

    map
      .getCanvas()
      .setAttribute(
        "aria-label",
        "Map of Kraków. Use the arrow keys to pan and the plus and minus keys to zoom.",
      );

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const handleZoomIn = useCallback(() => mapRef.current?.zoomIn(), []);
  const handleZoomOut = useCallback(() => mapRef.current?.zoomOut(), []);
  const handleRecenter = useCallback(() => {
    mapRef.current?.flyTo({ center: KRAKOW, zoom: ZOOM });
  }, []);

  return (
    <section className="map" aria-label="Map of Kraków">
      <div className="map__canvas" ref={containerRef} />
      <MapToolbar
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onRecenter={handleRecenter}
      />
    </section>
  );
}
