"""resolve report coordinates to a municipality using GUGiK's PRG boundaries."""

import logging
import re
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from http.client import HTTPException
from threading import Lock
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.common import Location

ULDK_URL = "https://uldk.gugik.gov.pl/"
TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 16_384
CACHE_TTL_SECONDS = 86_400
MAX_CACHE_ENTRIES = 4096
MAX_PENDING_LOOKUPS = 16
QUEUE_TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.5

logger = logging.getLogger(__name__)


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


class _TransientLookupError(MunicipalityUnavailableError):
    pass


def _lookup_municipality(location: Location) -> Municipality | None:
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
    except HTTPError as error:
        if error.code in (408, 429) or 500 <= error.code < 600:
            raise _TransientLookupError from error
        raise MunicipalityUnavailableError from error
    except (OSError, HTTPException) as error:
        raise _TransientLookupError from error
    except UnicodeError as error:
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


class MunicipalityResolver:
    def __init__(self) -> None:
        self._cache: OrderedDict[tuple[float, float], tuple[float, Municipality]] = OrderedDict()
        self._pending: dict[tuple[float, float], Future[Municipality | None]] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="municipality")

    def resolve(self, location: Location) -> Municipality | None:
        key = (location.longitude, location.latitude)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                if monotonic() - cached[0] < CACHE_TTL_SECONDS:
                    return cached[1]
            future = self._pending.get(key)
            if future is None:
                if len(self._pending) >= MAX_PENDING_LOOKUPS:
                    logger.warning("Municipality lookup queue is full")
                    if cached is not None:
                        return cached[1]
                    raise MunicipalityUnavailableError("Municipality lookup queue is full")
                deadline = monotonic() + QUEUE_TIMEOUT_SECONDS
                future = self._executor.submit(self._resolve, location, key, cached, deadline)
                self._pending[key] = future
        try:
            return future.result(timeout=QUEUE_TIMEOUT_SECONDS)
        except FutureTimeoutError as error:
            logger.warning("Municipality lookup queue wait timed out")
            if cached is not None:
                return cached[1]
            raise MunicipalityUnavailableError("Municipality lookup queue wait timed out") from error

    def _resolve(
        self,
        location: Location,
        key: tuple[float, float],
        cached: tuple[float, Municipality] | None,
        deadline: float,
    ) -> Municipality | None:
        try:
            for attempt in range(MAX_ATTEMPTS):
                if monotonic() >= deadline:
                    logger.warning("Municipality lookup expired in the queue")
                    if cached is not None:
                        return cached[1]
                    raise MunicipalityUnavailableError("Municipality lookup queue wait timed out")
                try:
                    municipality = _lookup_municipality(location)
                    break
                except _TransientLookupError as error:
                    logger.warning(
                        "Municipality lookup attempt %s/%s failed: %s",
                        attempt + 1,
                        MAX_ATTEMPTS,
                        type(error.__cause__).__name__,
                    )
                    if attempt + 1 == MAX_ATTEMPTS:
                        if cached is not None:
                            logger.warning("Using cached municipality after temporary lookup failures")
                            return cached[1]
                        raise
                    sleep(RETRY_DELAY_SECONDS * 2**attempt)
                except MunicipalityUnavailableError:
                    with self._lock:
                        self._cache.pop(key, None)
                    logger.warning("Municipality lookup returned an invalid or ambiguous response")
                    raise
            with self._lock:
                if municipality is None:
                    self._cache.pop(key, None)
                else:
                    self._cache[key] = (monotonic(), municipality)
                    self._cache.move_to_end(key)
                    while len(self._cache) > MAX_CACHE_ENTRIES:
                        self._cache.popitem(last=False)
            return municipality
        finally:
            with self._lock:
                self._pending.pop(key, None)


_resolver = MunicipalityResolver()


def resolve_municipality(location: Location) -> Municipality | None:
    return _resolver.resolve(location)
