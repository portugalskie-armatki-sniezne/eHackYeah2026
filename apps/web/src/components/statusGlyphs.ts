import type { MasterReportStatusName } from "../api/reports";

/** The grid the status pictograms are struck on. */
export const STATUS_GLYPH_VIEWBOX = "0 0 16 16";

// Struck with the pin's pen on a 16-unit grid: an open circle for a master only
// written down, an envelope once it is sent, a half-filled circle while the work
// is on, and a check when it is done. Markup rather than React nodes, so the
// status badge and the map pin, which builds its DOM by hand, draw the same
// shapes. Static constants: nothing user-supplied goes through here.
export const STATUS_GLYPHS: Record<MasterReportStatusName, string> = {
  created: `<circle cx="8" cy="8" r="5.5" />`,
  reported: `
    <rect x="2" y="4" width="12" height="9" />
    <path d="M2 4.5 L8 9 L14 4.5" />
  `,
  inprogress: `
    <circle cx="8" cy="8" r="5.5" />
    <path class="status-glyph__fill" d="M8 2.5 A5.5 5.5 0 0 1 8 13.5 Z" />
  `,
  finished: `<path d="M3 8.5 L6.5 12 L13 4.5" />`,
};

export function isStatusName(
  status: string | null | undefined,
): status is MasterReportStatusName {
  return status != null && status in STATUS_GLYPHS;
}
