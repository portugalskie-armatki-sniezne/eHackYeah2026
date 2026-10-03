"""resolve report coordinates to a municipality using GUGiK's PRG boundaries."""

import re
from dataclasses import dataclass
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.common import Location

ULDK_URL = "https://uldk.gugik.gov.pl/"
TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 16_384


@dataclass(frozen=True)
class Municipality:
    teryt: str
    name: str
    county_name: str

    @property
    def county_teryt(self) -> str:
        return self.teryt[:4]


class MunicipalityUnavailableError(Exception):
    pass


def resolve_municipality(location: Location) -> Municipality | None:
    query = urlencode(
        {
            "request": "GetCommuneByXY",
            "xy": f"{location.longitude},{location.latitude},4326",
            "result": "teryt,commune,county",
        }
    )
    request = Request(f"{ULDK_URL}?{query}", headers={"User-Agent": "eHackYeah2026/1.0"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise MunicipalityUnavailableError
        lines = data.decode("utf-8").strip().splitlines()
    except (OSError, HTTPException, UnicodeError) as error:
        raise MunicipalityUnavailableError from error

    if lines == ["-1 brak wyników"]:
        return None
    # multiple results at a boundary are ambiguous; never choose the first municipality.
    if len(lines) != 2 or lines[0] != "0":
        raise MunicipalityUnavailableError
    fields = lines[1].split("|")
    if len(fields) != 3:
        raise MunicipalityUnavailableError
    teryt, name, county_name = fields
    if not re.fullmatch(r"[0-9]{6}_[123]", teryt) or not name.strip() or not county_name.strip():
        raise MunicipalityUnavailableError
    return Municipality(teryt=teryt.replace("_", ""), name=name.strip(), county_name=county_name.strip())
