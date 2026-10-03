import "./MapToolbar.css";

export type BasemapId = "streets";

type BasemapOption = {
  id: BasemapId;
  label: string;
};

const basemaps: BasemapOption[] = [{ id: "streets", label: "Streets" }];

type MapToolbarProps = {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onRecenter: () => void;
};

export default function MapToolbar({
  onZoomIn,
  onZoomOut,
  onRecenter,
}: MapToolbarProps) {
  return (
    <div className="toolbar">
      <div className="toolbar__pill">
        <div className="toolbar__group" role="group" aria-label="Map controls">
          <button type="button" className="toolbar__button" onClick={onZoomOut}>
            <span aria-hidden="true">&minus;</span>
            <span className="visually-hidden">Zoom out</span>
          </button>
          <button type="button" className="toolbar__button" onClick={onZoomIn}>
            <span aria-hidden="true">+</span>
            <span className="visually-hidden">Zoom in</span>
          </button>
          <button
            type="button"
            className="toolbar__button toolbar__button--wide"
            onClick={onRecenter}
          >
            Recenter on Kraków
          </button>
        </div>
      </div>
    </div>
  );
}
