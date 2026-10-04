import type { ChangeEvent } from "react";
import { useMessages } from "../i18n/locale";
import MapFilters from "./MapFilters";
import type { MarkerFilters } from "./markerFilters";
import "./MapToolbar.css";

export type BasemapId = "streets";

type MapToolbarProps = {
  tilted: boolean;
  onToggleTilt: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onRecenter: () => void;
  onRecenterOnMe: () => void;
  /** False until the device has reported a position. */
  canRecenterOnMe: boolean;
  /** Asked when the "+" tile is pressed; false keeps the camera closed. */
  onPhotoReportStart: () => boolean;
  /** A photo taken with the "+" tile, to be pinned where the device is. */
  onPhotoReport: (photo: File) => void;
  /** Which kinds and statuses the map draws a pin for. */
  filters: MarkerFilters;
  onFiltersChange: (filters: MarkerFilters) => void;
  /** how many pins the filters leave on the map, out of every pin loaded */
  shownPins: number;
  totalPins: number;
  /** whether the filter list offers the box for the viewer's own cases */
  canFilterMine: boolean;
};

export default function MapToolbar({
  tilted,
  onToggleTilt,
  onZoomIn,
  onZoomOut,
  onRecenterOnMe,
  canRecenterOnMe,
  onPhotoReportStart,
  onPhotoReport,
  filters,
  onFiltersChange,
  shownPins,
  totalPins,
  canFilterMine,
}: MapToolbarProps) {
  const t = useMessages().toolbar;
  const handlePhotoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // cleared so the same photo can be taken again and still fire a change
    event.target.value = "";
    if (file) {
      onPhotoReport(file);
    }
  };

  return (
    <div className="toolbar">
      <div className="toolbar__frame">
        <div className="toolbar__group" role="group" aria-label={t.zoom}>
          <button type="button" className="toolbar__button" onClick={onZoomOut}>
            <span aria-hidden="true">&minus;</span>
            <span className="visually-hidden">{t.zoomOut}</span>
          </button>
          <button type="button" className="toolbar__button" onClick={onZoomIn}>
            <span aria-hidden="true">+</span>
            <span className="visually-hidden">{t.zoomIn}</span>
          </button>
        </div>
        {/* Phones only: the primary action sits in the middle of the row,
            between the zoom pair and the view controls. On wide screens the
            report flow starts elsewhere, so the tile and its divider go. */}
        <div className="toolbar__report">
          <span className="toolbar__divider" aria-hidden="true" />
          {/* The camera opens straight from the tile: the input is the control,
              and the tile is its label, so no click has to be forwarded. */}
          <label
            className="toolbar__add"
            aria-disabled={!canRecenterOnMe}
            title={canRecenterOnMe ? undefined : t.noFix}
          >
            <span className="toolbar__add-glyph" aria-hidden="true">
              +
            </span>
            <span className="visually-hidden">
              {canRecenterOnMe ? t.photoReport : t.photoReportWaiting}
            </span>
            <input
              className="visually-hidden"
              type="file"
              name="photo"
              accept="image/*"
              capture="environment"
              disabled={!canRecenterOnMe}
              onClick={(event) => {
                if (!onPhotoReportStart()) event.preventDefault();
              }}
              onChange={handlePhotoChange}
            />
          </label>
        </div>
        <span className="toolbar__divider" aria-hidden="true" />
        <div className="toolbar__group" role="group" aria-label={t.view}>
          <button
            type="button"
            className="toolbar__button toolbar__button--wide"
            onClick={onRecenterOnMe}
            disabled={!canRecenterOnMe}
            title={canRecenterOnMe ? undefined : t.noFix}
          >
            <svg
              className="toolbar__icon"
              viewBox="-10 -10 20 20"
              aria-hidden="true"
              focusable="false"
            >
              <path
                className="toolbar__icon-line"
                d="M-9 0 H-4 M4 0 H9 M0 -9 V-4 M0 4 V9"
              />
              <circle className="toolbar__icon-dot" r="2.25" />
            </svg>
            <span className="toolbar__label">{t.recenterOnMe}</span>
          </button>
          <span className="toolbar__divider" aria-hidden="true" />
          <button
            type="button"
            className="toolbar__choice"
            aria-pressed={tilted}
            onClick={onToggleTilt}
          >
            3D
          </button>
        </div>
        {/* Its own tile rather than one of the view controls: on a phone it
            leaves the row altogether for the sheet's bottom-left corner. */}
        <span
          className="toolbar__divider toolbar__divider--filters"
          aria-hidden="true"
        />
        <MapFilters
          filters={filters}
          onChange={onFiltersChange}
          shown={shownPins}
          total={totalPins}
          canFilterMine={canFilterMine}
        />
      </div>
    </div>
  );
}
