# /// script
# requires-python = ">=3.12"
# dependencies = ["pyproj==3.7.2"]
# ///
"""refresh the bundled Kraków district boundaries from the official MSIP download."""

import argparse
import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

from pyproj import Transformer

DOWNLOAD_URL = "https://msip.um.krakow.pl/Dane/Dzielnice_JSON.zip"
OUTPUT = Path(__file__).resolve().parents[1] / "src/data/krakow-districts.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--retrieved-on", type=date.fromisoformat)
    args = parser.parse_args()
    if args.archive and not args.retrieved_on:
        parser.error("--archive requires its original --retrieved-on date")
    if args.archive:
        archive = args.archive.read_bytes()
    else:
        with urlopen(DOWNLOAD_URL, timeout=30) as response:
            archive = response.read(10_000_001)
        if len(archive) > 10_000_000:
            raise ValueError("MSIP archive exceeds the size limit")
    with ZipFile(BytesIO(archive)) as files:
        collection = json.loads(files.read("Dzielnice.geojson"))
        freshness = files.read("__Aktualnosc__.txt").decode("utf-8")
    generated_at = re.search(r"\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2}", freshness)
    if not generated_at or collection["crs"]["properties"]["name"] != "EPSG:2178":
        raise ValueError("Unexpected source date or coordinate system")
    if collection["type"] != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    transform = Transformer.from_crs("EPSG:2178", "EPSG:4326", always_xy=True)
    features = []
    for feature in collection["features"]:
        properties = feature["properties"]
        geometry = feature["geometry"]
        if geometry["type"] not in ("Polygon", "MultiPolygon"):
            raise ValueError("Expected district polygons")
        polygons = (
            [geometry["coordinates"]]
            if geometry["type"] == "Polygon"
            else geometry["coordinates"]
        )
        converted = []
        for polygon in polygons:
            if not polygon:
                raise ValueError("Empty district polygon")
            rings = []
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("Invalid district ring")
                points = []
                for x, y in ring:
                    longitude, latitude = transform.transform(x, y, errcheck=True)
                    if not (
                        math.isfinite(longitude)
                        and math.isfinite(latitude)
                        and 19 < longitude < 21
                        and 49 < latitude < 51
                    ):
                        raise ValueError("Coordinates outside the Kraków region")
                    points.append([round(longitude, 7), round(latitude, 7)])
                rings.append(points)
            converted.append(rings)
        points = [point for polygon in converted for ring in polygon for point in ring]
        features.append(
            {
                "type": "Feature",
                "id": properties["id_dzielni"],
                "properties": {
                    "number": properties["id_dzielni"],
                    "name": properties["nazwa"],
                    "fullName": properties["nazwa_peln"],
                },
                "bbox": [
                    min(p[0] for p in points),
                    min(p[1] for p in points),
                    max(p[0] for p in points),
                    max(p[1] for p in points),
                ],
                "geometry": {
                    "type": geometry["type"],
                    "coordinates": converted[0]
                    if geometry["type"] == "Polygon"
                    else converted,
                },
            }
        )
    features.sort(key=lambda feature: feature["id"])
    if [feature["id"] for feature in features] != list(range(1, 19)):
        raise ValueError("Expected exactly Kraków districts I-XVIII")
    source = {
        "title": "Podział administracyjny - dzielnice",
        "url": "https://msip.krakow.pl/dataset/1483",
        "downloadUrl": DOWNLOAD_URL,
        "termsUrl": "https://msip.krakow.pl/getPdf?dok_id=228972",
        "attribution": "Gmina Miejska Kraków, Portal MSIP Obserwatorium",
        "retrievedOn": str(args.retrieved_on or datetime.now(timezone.utc).date()),
        "generatedAt": generated_at[0].replace("_", "T"),
        "archiveSha256": hashlib.sha256(archive).hexdigest(),
        "sourceCrs": "EPSG:2178",
        "outputCrs": "EPSG:4326",
    }
    header = json.dumps(
        {"type": "FeatureCollection", "source": source}, ensure_ascii=False, indent=2
    )
    rows = ",\n".join(
        "    " + json.dumps(f, ensure_ascii=False, separators=(",", ":"))
        for f in features
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        header[:-2] + ',\n  "features": [\n' + rows + "\n  ]\n}\n", encoding="utf-8"
    )
    print(f"Saved {len(features)} districts to {OUTPUT}")


if __name__ == "__main__":
    main()
