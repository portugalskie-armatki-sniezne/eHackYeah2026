import type { Map as MapLibreMap, PointLike } from "maplibre-gl";

/**
 * The disc layer ReportClusters draws its groups on. Kept out of that module so
 * Map can hit-test it without importing a component file, which fast refresh
 * wants to hold nothing but components.
 */
export const CLUSTER_DISC_LAYER = "report-cluster";

/** True when the point is on a group, which opens rather than starting a report. */
export function isClusterAt(map: MapLibreMap, point: PointLike): boolean {
  if (!map.getLayer(CLUSTER_DISC_LAYER)) {
    return false;
  }
  return (
    map.queryRenderedFeatures(point, { layers: [CLUSTER_DISC_LAYER] }).length >
    0
  );
}
