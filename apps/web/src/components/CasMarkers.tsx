import { useEffect, useEffectEvent, useRef, type RefObject } from "react";
import { Marker, type Map as MapLibreMap } from "maplibre-gl";
import { getCasInDistrict, type KrakowCasCenter } from "../data/krakowCas";
import "./CasMarkers.css";

type CasMarkersProps = {
  mapRef: RefObject<MapLibreMap | null>;
  styleReady: boolean;
  visible: boolean;
  selectedDistrict: number | null;
  onCasClick?: (cas: KrakowCasCenter) => void;
};

function casPinElement(
  cas: KrakowCasCenter,
  onClick: () => void,
): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "cas-pin";
  button.setAttribute("aria-label", `CAS: ${cas.name}, ${cas.address}`);
  button.title = `${cas.name} (${cas.address})`;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick();
  });

  const drop = document.createElement("div");
  drop.className = "cas-pin__drop";

  const needle = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  needle.setAttribute("class", "cas-pin__needle");
  needle.setAttribute("viewBox", "-16 -40 32 40");
  needle.setAttribute("aria-hidden", "true");
  needle.innerHTML = `
    <path class="cas-pin__needle-paper" d="M-4 -14 V-12 L0 0 L4 -12 V-14 Z" />
    <path class="cas-pin__needle-line" d="M-4 -12 L0 0 L4 -12" />
  `;

  const head = document.createElement("div");
  head.className = "cas-pin__head";
  head.innerHTML = `
    <svg class="cas-pin__icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
    </svg>
  `;

  drop.append(needle, head);
  button.append(drop);
  return button;
}

export default function CasMarkers({
  mapRef,
  styleReady,
  visible,
  selectedDistrict,
  onCasClick,
}: CasMarkersProps) {
  const markersRef = useRef(
    new globalThis.Map<number, { marker: Marker; cas: KrakowCasCenter }>(),
  );
  const handleOpenCas = useEffectEvent((cas: KrakowCasCenter) =>
    onCasClick?.(cas),
  );

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map) {
      return;
    }

    const markers = markersRef.current;

    if (!visible) {
      for (const entry of markers.values()) {
        entry.marker.remove();
      }
      markers.clear();
      return;
    }

    const wantedCenters = getCasInDistrict(selectedDistrict);
    const wantedIds = new Set(wantedCenters.map((c) => c.id));

    // Remove centers no longer wanted (e.g. filtered by district)
    for (const [id, entry] of markers) {
      if (!wantedIds.has(id)) {
        entry.marker.remove();
        markers.delete(id);
      }
    }

    // Add new centers
    for (const cas of wantedCenters) {
      if (markers.has(cas.id)) continue;
      const marker = new Marker({
        element: casPinElement(cas, () => handleOpenCas(cas)),
        anchor: "bottom",
      })
        .setLngLat(cas.coordinates)
        .addTo(map);

      markers.set(cas.id, { marker, cas });
    }
  }, [mapRef, styleReady, visible, selectedDistrict]);

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
