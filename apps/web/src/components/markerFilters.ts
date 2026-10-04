import type {
  MasterReportStatusName,
  ReportCategoryName,
} from "../api/reports";
import type { EventPin } from "./EventMarkers";

/** The two kinds of pin, in the order the filter list offers them. */
export const FILTER_CATEGORIES: readonly ReportCategoryName[] = [
  "issue",
  "improvement",
];

/** The four statuses, in the order a case moves through them. */
export const FILTER_STATUSES: readonly MasterReportStatusName[] = [
  "created",
  "reported",
  "inprogress",
  "finished",
];

/** Which kinds and statuses the map draws a pin for. */
export type MarkerFilters = {
  categories: ReadonlySet<ReportCategoryName>;
  statuses: ReadonlySet<MasterReportStatusName>;
};

/** Where the map opens: every pin is on it. */
export const ALL_MARKERS: MarkerFilters = {
  categories: new Set(FILTER_CATEGORIES),
  statuses: new Set(FILTER_STATUSES),
};

/** Every box cleared, which leaves the map bare. */
export const NO_MARKERS: MarkerFilters = {
  categories: new Set(),
  statuses: new Set(),
};

/** whether the filters still let everything through */
export function isEveryMarkerShown(filters: MarkerFilters): boolean {
  return (
    filters.categories.size === FILTER_CATEGORIES.length &&
    filters.statuses.size === FILTER_STATUSES.length
  );
}

/** whether every box is cleared */
export function isNoMarkerShown(filters: MarkerFilters): boolean {
  return filters.categories.size === 0 && filters.statuses.size === 0;
}

/** whether a pin survives the chosen filters */
export function matchesFilters(pin: EventPin, filters: MarkerFilters): boolean {
  if (!filters.categories.has(pin.category)) {
    return false;
  }
  // A master whose status the interface does not know has no box of its own, so
  // it stays on the map only while the status list is untouched.
  if (!pin.status) {
    return filters.statuses.size === FILTER_STATUSES.length;
  }
  return filters.statuses.has(pin.status);
}

/** the set with the value taken out, or put in when it was not there */
export function toggleFilter<T>(values: ReadonlySet<T>, value: T): Set<T> {
  const next = new Set(values);
  if (!next.delete(value)) {
    next.add(value);
  }
  return next;
}
