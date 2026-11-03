import { describe, expect, test } from "bun:test";
import {
  getCasInDistrict,
  krakowCasCenters,
  krakowCasGeoJSON,
  krakowCasSource,
} from "../src/data/krakowCas";

describe("Centra Aktywności Seniora (CAS) dataset", () => {
  test("contains all 68 centers with recorded source provenance", () => {
    expect(krakowCasCenters.length).toBe(68);
    expect(krakowCasSource.count).toBe(68);
    expect(krakowCasSource.portalUrl).toBe(
      "https://otwartedane.um.krakow.pl/zbiory-danych/centra-aktywnosci-seniora-w-krakowie",
    );
    expect(krakowCasSource.apiUrl).toBe(
      "https://api.um.krakow.pl/opendata-spoleczenstwo-centra-aktywnosci-seniora/v1/cas-lista",
    );
    expect(krakowCasSource.sha256).toMatch(/^[a-f0-9]{64}$/);
    expect(krakowCasGeoJSON.type).toBe("FeatureCollection");
    expect(krakowCasGeoJSON.features.length).toBe(68);
  });

  test("each center has valid WGS84 coordinates within Kraków bounds", () => {
    for (const cas of krakowCasCenters) {
      const [lng, lat] = cas.coordinates;
      expect(Number.isFinite(lng)).toBe(true);
      expect(Number.isFinite(lat)).toBe(true);
      expect(lng).toBeGreaterThan(19.7);
      expect(lng).toBeLessThan(20.3);
      expect(lat).toBeGreaterThan(49.95);
      expect(lat).toBeLessThan(50.15);
    }
  });

  test("each center has required municipal metadata", () => {
    for (const cas of krakowCasCenters) {
      expect(cas.id).toBeGreaterThan(0);
      expect(cas.name).toMatch(/^cas\b/i);
      expect(cas.operator.length).toBeGreaterThan(0);
      expect(cas.address.length).toBeGreaterThan(0);
      expect(cas.postalCode).toMatch(/^\d{2}-\d{3}$/);
      expect(cas.districtNumber).toBeGreaterThanOrEqual(1);
      expect(cas.districtNumber).toBeLessThanOrEqual(18);
    }
  });

  test("filters centers by district correctly", () => {
    const all = getCasInDistrict(null);
    expect(all.length).toBe(68);

    const stareMiasto = getCasInDistrict(1);
    expect(stareMiasto.length).toBeGreaterThan(0);
    expect(stareMiasto.every((c) => c.districtNumber === 1)).toBe(true);

    const nowaHuta = getCasInDistrict(18);
    expect(nowaHuta.length).toBeGreaterThan(0);
    expect(nowaHuta.every((c) => c.districtNumber === 18)).toBe(true);
  });
});
