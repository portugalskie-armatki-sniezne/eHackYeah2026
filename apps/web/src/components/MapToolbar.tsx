import "./MapToolbar.css";

export type BasemapId = "streets";

type BasemapOption = {
  id: BasemapId;
  label: string;
};

const basemaps: BasemapOption[] = [{ id: "streets", label: "Streets" }];

type MapToolbarProps = {
  tilted: boolean;
  onToggleTilt: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onRecenter: () => void;
  onRecenterOnMe: () => void;
  /** False until the device has reported a position. */
  canRecenterOnMe: boolean;
};

export default function MapToolbar({
  tilted,
  onToggleTilt,
  onZoomIn,
  onZoomOut,
  onRecenter,
  onRecenterOnMe,
  canRecenterOnMe,
}: MapToolbarProps) {
  return (
    <div className="toolbar">
      <div className="toolbar__frame">
        <div className="toolbar__group" role="group" aria-label="Map controls">
          <button type="button" className="toolbar__button" onClick={onZoomOut}>
            <span aria-hidden="true">&minus;</span>
            <span className="visually-hidden">Zoom out</span>
          </button>
          <button type="button" className="toolbar__button" onClick={onZoomIn}>
            <span aria-hidden="true">+</span>
            <span className="visually-hidden">Zoom in</span>
          </button>
          <span className="toolbar__divider" aria-hidden="true" />
          <button
            type="button"
            className="toolbar__button toolbar__button--wide"
            onClick={onRecenter}
          >
            Recenter on Kraków
          </button>
          <button
            type="button"
            className="toolbar__button toolbar__button--wide"
            onClick={onRecenterOnMe}
            disabled={!canRecenterOnMe}
            title={canRecenterOnMe ? undefined : "No location fix yet"}
          >
            Recenter on me
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
      </div>
    </div>
  );
}
