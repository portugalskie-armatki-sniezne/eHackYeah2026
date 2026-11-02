import type { ReportLocation } from "../api/reports";
import snapshot from "./krakow-districts.json";

export type KrakowDistrict = {
  number: number;
  name: string;
  fullName: string;
};

type Position = number[];
type DistrictCollection = {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    id: number;
    properties: KrakowDistrict;
    bbox: [number, number, number, number];
    geometry:
      | { type: "Polygon"; coordinates: Position[][] }
      | { type: "MultiPolygon"; coordinates: Position[][][] };
  }[];
};

export const krakowDistrictSource = snapshot.source;
export const krakowDistrictGeoJSON = snapshot as unknown as DistrictCollection;
export const krakowDistricts = krakowDistrictGeoJSON.features.map(
  (feature) => feature.properties,
);

// ring position: -1 outside, 0 on the boundary, 1 inside; longitude, latitude
function ringPosition([x, y]: Position, ring: Position[]): -1 | 0 | 1 {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[j];
    const [bx, by] = ring[i];
    const dx = bx - ax;
    const dy = by - ay;
    const length = Math.hypot(dx, dy);
    if (
      length > 0 &&
      Math.abs((x - ax) * dy - (y - ay) * dx) / length <= 1e-10 &&
      x >= Math.min(ax, bx) - 1e-10 &&
      x <= Math.max(ax, bx) + 1e-10 &&
      y >= Math.min(ay, by) - 1e-10 &&
      y <= Math.max(ay, by) + 1e-10
    ) {
      return 0;
    }
    if (ay > y !== by > y && x < ((bx - ax) * (y - ay)) / (by - ay) + ax) {
      inside = !inside;
    }
  }
  return inside ? 1 : -1;
}

export function polygonCoversPoint(
  point: Position,
  rings: Position[][],
): boolean {
  const [outer, ...holes] = rings;
  if (!outer || ringPosition(point, outer) === -1) return false;
  return holes.every((hole) => ringPosition(point, hole) !== 1);
}

export function krakowDistrictAt({
  longitude,
  latitude,
}: ReportLocation): KrakowDistrict | null {
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return null;
  const point = [longitude, latitude];
  for (const { properties, geometry, bbox } of krakowDistrictGeoJSON.features) {
    if (
      bbox &&
      (longitude < bbox[0] ||
        latitude < bbox[1] ||
        longitude > bbox[2] ||
        latitude > bbox[3])
    ) {
      continue;
    }
    const polygons =
      geometry.type === "Polygon"
        ? [geometry.coordinates]
        : geometry.coordinates;
    if (polygons.some((rings) => polygonCoversPoint(point, rings)))
      return properties;
  }
  return null;
}
