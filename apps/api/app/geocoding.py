"""resolve unambiguous seat addresses through GUGiK for the catalog import."""

import json
import math
import re
from dataclasses import dataclass
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UUG_URL = "https://services.gugik.gov.pl/uug/"
TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 65_536


class GeocodingUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class AddressPoint:
    # UUG returns easting and northing in EPSG:2180.
    x: float
    y: float


def normalized_street(street: str | None) -> str:
    value = (street or "").strip().casefold()
    value = re.sub(r"^ul(?:ica)?\.?\s+", "", value)
    for abbreviation, full in (("al", "aleja"), ("pl", "plac"), ("os", "osiedle")):
        value = re.sub(rf"^{abbreviation}\.\s+", full + " ", value)
    return " ".join(value.split())


def address_point(
    locality: str, street: str | None, number: str, postal_code: str | None = None
) -> AddressPoint | None:
    street = normalized_street(street)
    address = f"{locality}, {street} {number}" if street else f"{locality} {number}"
    query = urlencode({"request": "GetAddress", "address": address, "accuracy": "0.8", "exact_number": "1"})
    request = Request(f"{UUG_URL}?{query}", headers={"User-Agent": "eHackYeah2026/1.0"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise GeocodingUnavailableError
        payload = json.loads(data)
        if (
            isinstance(payload, dict)
            and payload.get("type") == "address"
            and payload.get("returned objects") == 0
            and payload.get("results") is None
        ):
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), dict):
            raise GeocodingUnavailableError
        results = list(payload["results"].values())
        if not results:
            return None
        if payload.get("type") != "address":
            return None
        candidates = []
        for result in results:
            if not isinstance(result, dict):
                raise GeocodingUnavailableError
            accuracy = float(result["accuracy"])
            if not math.isfinite(accuracy) or not 0 <= accuracy <= 1:
                raise GeocodingUnavailableError
            # UUG also returns alternatives below the requested accuracy threshold.
            if (
                str(result["number"]).casefold() == number.strip().casefold()
                and str(result["city"]).casefold() == locality.strip().casefold()
                and normalized_street(result.get("street")) == street
                and accuracy >= 0.8
            ):
                candidates.append(result)
        if len(candidates) > 1 and postal_code:
            candidates = [result for result in candidates if result.get("code") == postal_code]
        if len(candidates) != 1:
            return None
        result = candidates[0]
        x, y = float(result["x"]), float(result["y"])
        if not math.isfinite(x) or not math.isfinite(y) or not (0 < x < 1_000_000 and 0 < y < 1_000_000):
            raise GeocodingUnavailableError
        return AddressPoint(x=x, y=y)
    except (OSError, HTTPException, ValueError, KeyError, TypeError) as error:
        raise GeocodingUnavailableError from error
