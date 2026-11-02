import { useMessages } from "../i18n/locale";
import {
  STATUS_GLYPH_VIEWBOX,
  STATUS_GLYPHS,
  isStatusName,
} from "./statusGlyphs";
import "./StatusBadge.css";

type StatusBadgeProps = {
  /** a name outside the known four is shown as it comes, with no pictogram */
  status: string | null;
};

/**
 * The master's status as a tile with its pictogram. The map pin draws the same
 * pictogram in the same colour, so a case reads alike in the list and on the map.
 */
export default function StatusBadge({ status }: StatusBadgeProps) {
  const t = useMessages().status;
  if (status === null) {
    return (
      <span className="status-badge status-badge--unknown">{t.unknown}</span>
    );
  }
  if (!isStatusName(status)) {
    return <span className="status-badge">{status}</span>;
  }
  return (
    <span className={`status-badge status-badge--${status}`}>
      <svg
        className="status-badge__glyph"
        viewBox={STATUS_GLYPH_VIEWBOX}
        aria-hidden="true"
        // static markup shared with the pin, see statusGlyphs.ts
        dangerouslySetInnerHTML={{ __html: STATUS_GLYPHS[status] }}
      />
      {t[status]}
    </span>
  );
}
