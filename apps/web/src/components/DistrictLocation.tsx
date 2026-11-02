import type { ReportLocation } from "../api/reports";
import {
  krakowDistrictAt,
  krakowDistrictSource,
} from "../data/krakowDistricts";
import { useMessages } from "../i18n/locale";
import "./DistrictLocation.css";

export default function DistrictLocation({
  location,
}: {
  location: ReportLocation;
}) {
  const t = useMessages().districts;
  const district = krakowDistrictAt(location);

  return (
    <aside className="district-location" aria-label={t.heading}>
      <strong>{district?.fullName ?? t.outside}</strong>
      <a
        href={krakowDistrictSource.url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {t.source}: {krakowDistrictSource.attribution}
      </a>
    </aside>
  );
}
