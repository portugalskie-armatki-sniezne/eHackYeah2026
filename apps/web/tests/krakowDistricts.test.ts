import { describe, expect, test } from "bun:test";
import {
  krakowDistrictAt,
  krakowDistrictGeoJSON,
  krakowDistricts,
  krakowDistrictSource,
  polygonCoversPoint,
} from "../src/data/krakowDistricts";

describe("MSIP district boundaries", () => {
  test("contains all 18 official districts with recorded source provenance", () => {
    expect(krakowDistricts.map((district) => district.number)).toEqual(
      Array.from({ length: 18 }, (_, index) => index + 1),
    );
    expect(krakowDistrictSource.url).toBe(
      "https://msip.krakow.pl/dataset/1483",
    );
    expect(krakowDistrictSource.sourceCrs).toBe("EPSG:2178");
    expect(krakowDistrictSource.outputCrs).toBe("EPSG:4326");
    expect(krakowDistrictSource.archiveSha256).toMatch(/^[a-f0-9]{64}$/);
  });

  test.each([
    ["Rynek Główny", 19.937, 50.0617, 1, "Stare Miasto"],
    ["Rondo Mogilskie", 19.96, 50.064, 2, "Grzegórzki"],
    ["Krowodrza", 19.922, 50.075, 5, "Krowodrza"],
    ["Ruczaj", 19.903, 50.02, 8, "Dębniki"],
    ["Rynek Podgórski", 19.951, 50.043, 13, "Podgórze"],
    ["Plac Centralny", 20.037, 50.072, 18, "Nowa Huta"],
  ])(
    "recognizes %s using WGS 84 coordinates",
    (_, longitude, latitude, number, name) => {
      expect(krakowDistrictAt({ longitude, latitude })).toMatchObject({
        number,
        name,
      });
    },
  );

  test.each([
    [20.064, 49.987],
    [16.929, 52.407],
    [0, 0],
    [50.0617, 19.937],
    [NaN, 50.0617],
    [19.937, Infinity],
  ])(
    "does not assign a district to outside or invalid coordinates %s, %s",
    (longitude, latitude) => {
      expect(krakowDistrictAt({ longitude, latitude })).toBeNull();
    },
  );

  test("accepts a real boundary vertex with a deterministic district", () => {
    const first = krakowDistrictGeoJSON.features[0];
    const ring =
      first.geometry.type === "Polygon"
        ? first.geometry.coordinates[0]
        : first.geometry.coordinates[0][0];
    const [longitude, latitude] = ring[0];
    expect(krakowDistrictAt({ longitude, latitude })?.number).toBe(1);
  });

  test("handles holes, closed rings, horizontal edges and shared vertices", () => {
    const polygon = [
      [
        [0, 0],
        [4, 0],
        [4, 4],
        [0, 4],
        [0, 0],
      ],
      [
        [1, 1],
        [3, 1],
        [3, 3],
        [1, 3],
        [1, 1],
      ],
    ];
    expect(polygonCoversPoint([0.5, 0.5], polygon)).toBe(true);
    expect(polygonCoversPoint([2, 2], polygon)).toBe(false);
    expect(polygonCoversPoint([0, 0], polygon)).toBe(true);
    expect(polygonCoversPoint([2, 0], polygon)).toBe(true);
    expect(polygonCoversPoint([1, 2], polygon)).toBe(true);
    expect(polygonCoversPoint([5, 2], polygon)).toBe(false);
  });
});
