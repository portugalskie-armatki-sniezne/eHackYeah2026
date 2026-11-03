# /// script
# requires-python = ">=3.12"
# dependencies = ["pyproj==3.8.0"]
# ///
"""Refresh the bundled Centra Aktywności Seniora (CAS) dataset from Kraków Open Data."""

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from pyproj import Transformer

API_METADATA_URL = (
    "https://api.um.krakow.pl/opendata-spoleczenstwo-centra-aktywnosci-seniora/v1/metadata"
)
API_DATA_URL = (
    "https://api.um.krakow.pl/opendata-spoleczenstwo-centra-aktywnosci-seniora/v1/cas-lista"
)
PORTAL_URL = (
    "https://otwartedane.um.krakow.pl/zbiory-danych/centra-aktywnosci-seniora-w-krakowie"
)
OUTPUT = Path(__file__).resolve().parents[1] / "src/data/krakow-cas.json"

ROMAN_TO_INT = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
}


def query_gugik(transformer: Transformer, query_address: str) -> tuple[float, float] | None:
    params = urllib.parse.urlencode({
        "request": "GetAddress",
        "address": f"Kraków, {query_address}",
        "accuracy": "0.3",
    })
    url = f"https://services.gugik.gov.pl/uug/?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "eHackYeah2026/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results", {})
        if results:
            first = list(results.values())[0]
            x, y = float(first["x"]), float(first["y"])
            lon, lat = transformer.transform(x, y)
            if 19.5 < lon < 20.3 and 49.9 < lat < 50.2:
                return round(lon, 7), round(lat, 7)
    except Exception:
        pass
    return None


def resolve_coordinates(transformer: Transformer, item: dict) -> tuple[float, float]:
    street = (item.get("Ulica") or "").strip()
    num = (item.get("Numer budynku") or "").strip()
    addr = (item.get("Adres") or "").strip()

    # 1. Clean street and num
    clean_street = re.sub(
        r"^(?:ul\.|aleja|al\.|os\.|osiedle)\s*", "", street, flags=re.I
    )
    clean_street = re.sub(r"\s+", " ", clean_street).strip()
    clean_num = re.sub(r"[/\\-].*$", "", num).strip()

    if clean_street and clean_num:
        coords = query_gugik(transformer, f"{clean_street} {clean_num}")
        if coords:
            return coords

    # 2. Try raw Adres cleaned
    if addr:
        clean_addr = re.sub(r"[/\\-].*$", "", addr).strip()
        coords = query_gugik(transformer, clean_addr)
        if coords:
            return coords
        sub_addr = re.sub(r"/\d+.*$", "", addr).strip()
        coords = query_gugik(transformer, sub_addr)
        if coords:
            return coords

    # 3. Try street alone
    if clean_street:
        coords = query_gugik(transformer, clean_street)
        if coords:
            return coords

    raise ValueError(f"Could not geocode CAS item: {item.get('Nazwa')} ({addr})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, help="Use existing JSON payload instead of fetching API")
    args = parser.parse_args()

    transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

    if args.input_file:
        raw_bytes = args.input_file.read_bytes()
        items = json.loads(raw_bytes.decode("utf-8"))
        metadata = {}
    else:
        req_meta = urllib.request.Request(API_METADATA_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_meta, timeout=15) as resp:
            meta_json = json.loads(resp.read().decode("utf-8"))
            metadata = meta_json.get("value", [{}])[0]

        req_data = urllib.request.Request(API_DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_data, timeout=30) as resp:
            raw_bytes = resp.read()
            data_json = json.loads(raw_bytes.decode("utf-8"))
            items = data_json.get("value", [])

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    today_str = date.today().isoformat()
    last_refresh = metadata.get("last_refresh") or datetime.now(timezone.utc).isoformat()

    features = []
    for item in items:
        lon, lat = resolve_coordinates(transformer, item)
        district_roman = (item.get("Dzielnica") or "").strip().upper()
        district_number = ROMAN_TO_INT.get(district_roman, 0)

        cas_id = int(item.get("Lp") or item.get("Numer pozycji CAS") or len(features) + 1)
        name = (item.get("Nazwa") or "").strip().replace("\xa0", " ")
        operator = (item.get("Podmiot prowadzący") or "").strip().replace("\xa0", " ")
        address = (item.get("Adres") or "").strip()
        postal_code = (item.get("Kod pocztowy") or "").strip()
        phone = (item.get("Kontakt 1") or item.get("Kontakt 2") or "").strip()
        notes = (item.get("Uwagi") or "").strip() or None

        features.append({
            "type": "Feature",
            "id": cas_id,
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "id": cas_id,
                "name": name,
                "operator": operator,
                "districtNumber": district_number,
                "districtRoman": district_roman,
                "districtName": (item.get("Nazwa dzielnicy") or "").strip(),
                "address": address,
                "postalCode": postal_code,
                "phone": phone if phone else None,
                "notes": notes,
                "coordinates": [lon, lat],
            },
        })

    features.sort(key=lambda f: f["id"])

    bundle = {
        "source": {
            "name": "Centra Aktywności Seniora w Krakowie",
            "authority": "Gmina Miejska Kraków, Urząd Miasta Krakowa, Wydział Polityki Społecznej i Zdrowia",
            "portalUrl": PORTAL_URL,
            "apiUrl": API_DATA_URL,
            "retrievedOn": today_str,
            "lastRefresh": last_refresh,
            "sha256": sha256,
            "termsUrl": "https://otwartedane.um.krakow.pl/warunki-korzystania",
            "count": len(features),
        },
        "type": "FeatureCollection",
        "features": features,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Successfully generated {OUTPUT} with {len(features)} CAS locations.")


if __name__ == "__main__":
    main()
