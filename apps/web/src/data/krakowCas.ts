import snapshot from "./krakow-cas.json";

export type KrakowCasCenter = {
  id: number;
  name: string;
  operator: string;
  districtNumber: number;
  districtRoman: string;
  districtName: string;
  address: string;
  postalCode: string;
  phone: string | null;
  notes: string | null;
  coordinates: [number, number]; // [longitude, latitude]
};

export type KrakowCasSource = {
  name: string;
  authority: string;
  portalUrl: string;
  apiUrl: string;
  retrievedOn: string;
  lastRefresh: string;
  sha256: string;
  termsUrl: string;
  count: number;
};

export type KrakowCasFeature = {
  type: "Feature";
  id: number;
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: KrakowCasCenter;
};

export type KrakowCasCollection = {
  type: "FeatureCollection";
  source: KrakowCasSource;
  features: KrakowCasFeature[];
};

export const krakowCasSource = snapshot.source as KrakowCasSource;
export const krakowCasGeoJSON = snapshot as unknown as KrakowCasCollection;
export const krakowCasCenters: KrakowCasCenter[] = snapshot.features.map(
  (feature) => feature.properties as unknown as KrakowCasCenter,
);

export function getCasInDistrict(
  districtNumber: number | null,
): KrakowCasCenter[] {
  if (districtNumber === null) return krakowCasCenters;
  return krakowCasCenters.filter(
    (cas) => cas.districtNumber === districtNumber,
  );
}
