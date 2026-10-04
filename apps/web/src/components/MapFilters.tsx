import { useEffect, useId, useRef, useState } from "react";
import { useMessages } from "../i18n/locale";
import {
  ALL_MARKERS,
  FILTER_CATEGORIES,
  FILTER_STATUSES,
  NO_MARKERS,
  isEveryMarkerShown,
  isNoMarkerShown,
  toggleFilter,
  type MarkerFilters,
} from "./markerFilters";
import { STATUS_GLYPH_VIEWBOX, STATUS_GLYPHS } from "./statusGlyphs";
import "./MapFilters.css";

type MapFiltersProps = {
  filters: MarkerFilters;
  onChange: (filters: MarkerFilters) => void;
  /** how many pins the filters leave on the map, out of every pin loaded */
  shown: number;
  total: number;
  /**
   * Whether the author box is offered: only for a signed-in account whose own
   * cases are known, since for anyone else it would simply empty the map.
   */
  canFilterMine: boolean;
};

/**
 * The toolbar's filter tile and the list it unfolds: a box per kind and per
 * status, plus the one that narrows the map to the viewer's own cases, ticked
 * for what the map draws. It closes on Escape, on a click elsewhere, and when
 * focus leaves it, like the navbar's account menu.
 */
export default function MapFilters({
  filters,
  onChange,
  shown,
  total,
  canFilterMine,
}: MapFiltersProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const t = useMessages();
  const f = t.filters;
  const narrowed = !isEveryMarkerShown(filters);

  useEffect(() => {
    if (!open) {
      return;
    }
    const closeOnOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", closeOnOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div
      ref={rootRef}
      className="toolbar__filters"
      onBlur={(event) => {
        // A click on a row blurs the tile with nothing taking focus, which must
        // not fold the list up under the pointer, so only focus landing on
        // something outside closes it.
        if (
          event.relatedTarget &&
          !event.currentTarget.contains(event.relatedTarget)
        ) {
          setOpen(false);
        }
      }}
    >
      <button
        ref={toggleRef}
        type="button"
        // the tile keeps its name once the words are dropped on narrow screens
        aria-label={f.open}
        title={f.open}
        aria-expanded={open}
        aria-controls={panelId}
        className={
          narrowed
            ? "toolbar__choice map-filters__toggle map-filters__toggle--narrowed"
            : "toolbar__choice map-filters__toggle"
        }
        onClick={() => setOpen((current) => !current)}
      >
        <svg
          className="toolbar__icon"
          viewBox="-10 -10 20 20"
          aria-hidden="true"
          focusable="false"
        >
          <path
            className="toolbar__icon-line"
            d="M-8 -6 H8 M-5 0 H5 M-2 6 H2"
          />
        </svg>
        <span className="toolbar__label">{f.label}</span>
      </button>
      <div id={panelId} className="map-filters" hidden={!open}>
        <p className="map-filters__heading">{f.heading}</p>
        <fieldset className="map-filters__group">
          <legend className="map-filters__legend">{f.kind}</legend>
          {FILTER_CATEGORIES.map((category) => (
            <label key={category} className="map-filters__row">
              <input
                type="checkbox"
                checked={filters.categories.has(category)}
                onChange={() =>
                  onChange({
                    ...filters,
                    categories: toggleFilter(filters.categories, category),
                  })
                }
              />
              <span className="map-filters__name">{f.kinds[category]}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="map-filters__group">
          <legend className="map-filters__legend">{f.status}</legend>
          {FILTER_STATUSES.map((status) => (
            <label
              key={status}
              className={`map-filters__row map-filters__row--${status}`}
            >
              <input
                type="checkbox"
                checked={filters.statuses.has(status)}
                onChange={() =>
                  onChange({
                    ...filters,
                    statuses: toggleFilter(filters.statuses, status),
                  })
                }
              />
              <svg
                className="map-filters__glyph"
                viewBox={STATUS_GLYPH_VIEWBOX}
                aria-hidden="true"
                // static markup shared with the pin, see statusGlyphs.ts
                dangerouslySetInnerHTML={{ __html: STATUS_GLYPHS[status] }}
              />
              <span className="map-filters__name">{t.status[status]}</span>
            </label>
          ))}
        </fieldset>
        {canFilterMine && (
          <fieldset className="map-filters__group">
            <legend className="map-filters__legend">{f.author}</legend>
            <label className="map-filters__row">
              <input
                type="checkbox"
                checked={filters.mineOnly}
                onChange={(event) =>
                  onChange({ ...filters, mineOnly: event.target.checked })
                }
              />
              <span className="map-filters__name">{f.onlyMine}</span>
            </label>
          </fieldset>
        )}
        <p className="map-filters__count">{f.shown(shown, total)}</p>
        <div className="map-filters__actions">
          <button
            type="button"
            className="map-filters__action"
            disabled={!narrowed}
            onClick={() => onChange(ALL_MARKERS)}
          >
            {f.selectAll}
          </button>
          <button
            type="button"
            className="map-filters__action"
            disabled={isNoMarkerShown(filters)}
            onClick={() => onChange(NO_MARKERS)}
          >
            {f.clear}
          </button>
        </div>
      </div>
    </div>
  );
}
