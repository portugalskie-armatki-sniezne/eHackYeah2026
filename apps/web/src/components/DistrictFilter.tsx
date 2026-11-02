import { useEffect, useId, type RefObject } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import {
  krakowDistrictGeoJSON,
  krakowDistricts,
  krakowDistrictSource,
} from "../data/krakowDistricts";
import { useMessages } from "../i18n/locale";
import "./DistrictFilter.css";

const SOURCE = "krakow-districts";
const FILL = "krakow-district-fill";
const OUTLINE = "krakow-district-outline";

type DistrictFilterProps = {
  mapRef: RefObject<MapLibreMap | null>;
  styleReady: boolean;
  selected: number | null;
  counts: ReadonlyMap<number, number>;
  visibleCount: number;
  loading: boolean;
  failed: boolean;
  onChange: (district: number | null) => void;
};

export default function DistrictFilter({
  mapRef,
  styleReady,
  selected,
  counts,
  visibleCount,
  loading,
  failed,
  onChange,
}: DistrictFilterProps) {
  const id = useId();
  const t = useMessages().districts;

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady) return;
    const sync = () => {
      if (!map.getSource(SOURCE)) {
        map.addSource(SOURCE, { type: "geojson", data: krakowDistrictGeoJSON });
      }
      if (!map.getLayer(FILL)) {
        map.addLayer({
          id: FILL,
          type: "fill",
          source: SOURCE,
          paint: { "fill-color": "#efb33f", "fill-opacity": 0.12 },
        });
      }
      if (!map.getLayer(OUTLINE)) {
        map.addLayer({
          id: OUTLINE,
          type: "line",
          source: SOURCE,
          paint: {
            "line-color": "#4a4a46",
            "line-width": 1.5,
            "line-dasharray": [3, 2],
          },
        });
      }
      map.setFilter(FILL, ["==", ["get", "number"], selected ?? -1]);
      map.setFilter(
        OUTLINE,
        selected === null ? null : ["==", ["get", "number"], selected],
      );
    };
    sync();
    map.on("style.load", sync);
    return () => {
      map.off("style.load", sync);
      if (map.getLayer(OUTLINE)) map.removeLayer(OUTLINE);
      if (map.getLayer(FILL)) map.removeLayer(FILL);
      if (map.getSource(SOURCE)) map.removeSource(SOURCE);
    };
  }, [mapRef, styleReady, selected]);

  const selectDistrict = (number: number | null) => {
    onChange(number);
    const feature = krakowDistrictGeoJSON.features.find(
      (item) => item.properties.number === number,
    );
    const bbox = feature?.bbox;
    if (bbox) {
      mapRef.current?.fitBounds(
        [
          [bbox[0], bbox[1]],
          [bbox[2], bbox[3]],
        ],
        {
          padding: { top: 170, bottom: 230, left: 40, right: 40 },
          maxZoom: 14,
        },
      );
    }
  };

  return (
    <aside className="district-filter" aria-label={t.heading}>
      <label htmlFor={id}>{t.filter}</label>
      <select
        id={id}
        value={selected ?? ""}
        onChange={(event) =>
          selectDistrict(event.target.value ? Number(event.target.value) : null)
        }
      >
        <option value="">{t.all}</option>
        {krakowDistricts.map((district) => (
          <option key={district.number} value={district.number}>
            {district.fullName} ({counts.get(district.number) ?? 0})
          </option>
        ))}
      </select>
      <span role="status">
        {failed
          ? t.loadError
          : loading
            ? t.loading
            : selected !== null && visibleCount === 0
              ? t.empty
              : t.caseCount(visibleCount)}
      </span>
      <a
        href={krakowDistrictSource.url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {t.boundariesSource}
      </a>
    </aside>
  );
}
