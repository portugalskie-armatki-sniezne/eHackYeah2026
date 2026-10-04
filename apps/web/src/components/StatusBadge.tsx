import type { ReactNode } from "react";
import type { MasterReportStatusName } from "../api/reports";
import "./StatusBadge.css";

type StatusBadgeProps = {
  /** a name outside the known four is shown as it comes, with no pictogram */
  status: string | null;
};

const LABELS: Record<MasterReportStatusName, string> = {
  created: "Created",
  reported: "Reported",
  inprogress: "In progress",
  finished: "Finished",
};

// Struck with the pin's pen on a 16-unit grid: an open circle for a master only
// written down, an envelope once it is sent, a half-filled circle while the work
// is on, and a check when it is done.
const GLYPHS: Record<MasterReportStatusName, ReactNode> = {
  created: <circle cx="8" cy="8" r="5.5" />,
  reported: (
    <>
      <rect x="2" y="4" width="12" height="9" />
      <path d="M2 4.5 L8 9 L14 4.5" />
    </>
  ),
  inprogress: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path className="status-badge__fill" d="M8 2.5 A5.5 5.5 0 0 1 8 13.5 Z" />
    </>
  ),
  finished: <path d="M3 8.5 L6.5 12 L13 4.5" />,
};

function isKnown(status: string): status is MasterReportStatusName {
  return status in LABELS;
}

/** The master's status as a tile with its pictogram. */
export default function StatusBadge({ status }: StatusBadgeProps) {
  if (status === null) {
    return <span className="status-badge status-badge--unknown">Unknown</span>;
  }
  if (!isKnown(status)) {
    return <span className="status-badge">{status}</span>;
  }
  return (
    <span className={`status-badge status-badge--${status}`}>
      <svg
        className="status-badge__glyph"
        viewBox="0 0 16 16"
        aria-hidden="true"
      >
        {GLYPHS[status]}
      </svg>
      {LABELS[status]}
    </span>
  );
}
