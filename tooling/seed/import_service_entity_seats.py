"""validate and import reviewed seat coordinates without network lookups."""

from datetime import date
import json
import math
from pathlib import Path
import re
from typing import TYPE_CHECKING

from import_service_entities import http_url

if TYPE_CHECKING:
    import psycopg


def validate_seats(seats: list[dict], entities: list[dict]) -> list[dict]:
    catalog = {e["source_key"]: [e["locality"], e["street"], e["house_number"]] for e in entities}
    if not isinstance(seats, list) or len(seats) != len(catalog):
        raise ValueError("Seat snapshot must cover every catalog entry")
    seen = set()
    for seat in seats:
        if not isinstance(seat, dict) or set(seat) != {
            "source_key", "address", "location", "municipality_teryt", "verified_on", "source_urls", "note",
        }:
            raise ValueError("Unexpected seat fields")
        key = seat["source_key"]
        if key not in catalog or key in seen or seat["address"] != catalog[key]:
            raise ValueError(f"Unknown, duplicate, or stale seat: {key}")
        seen.add(key)
        if not isinstance(seat["note"], str) or not seat["note"].strip():
            raise ValueError(f"Missing seat review note: {key}")
        if not isinstance(seat["source_urls"], list) or not seat["source_urls"] or any(
            not isinstance(url, str) or not http_url(url) for url in seat["source_urls"]
        ):
            raise ValueError(f"Invalid seat sources: {key}")
        if not isinstance(seat["verified_on"], str) or date.fromisoformat(seat["verified_on"]) > date.today():
            raise ValueError(f"Invalid seat date: {key}")
        location, teryt = seat["location"], seat["municipality_teryt"]
        if location is None and teryt is None:
            continue
        if not isinstance(teryt, str) or not re.fullmatch(r"[0-9]{7}", teryt):
            raise ValueError(f"Invalid seat municipality: {key}")
        if not isinstance(location, dict) or set(location) != {"longitude", "latitude"}:
            raise ValueError(f"Invalid seat coordinates: {key}")
        for field, low, high in (("longitude", -180, 180), ("latitude", -90, 90)):
            value = location[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low < value < high:
                raise ValueError(f"Invalid seat coordinate: {key}")
    return seats


def read_seats(path: Path, entities: list[dict]) -> list[dict]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if snapshot.get("format_version") != 1:
        raise ValueError("Unsupported seat snapshot format")
    return validate_seats(snapshot["seats"], entities)


def import_seats(connection: "psycopg.Connection", seats: list[dict], entities: list[dict]) -> int:
    from psycopg.types.json import Jsonb

    validate_seats(seats, entities)
    changed = 0
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('service_entities_seed', 0))")
        for seat in seats:
            if seat["location"] is None:
                # preserve independently verified live seats for unresolved snapshot entries.
                continue
            location = seat["location"]
            changed += connection.execute(
                "UPDATE service_entities SET seat_location = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, "
                "seat_teryt = %s, seat_address = %s, seat_geocoded_at = %s::date "
                "WHERE source_key = %s AND jsonb_build_array(locality, street, house_number) = %s "
                "AND (seat_location IS DISTINCT FROM ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography "
                "OR seat_teryt IS DISTINCT FROM %s OR seat_address IS DISTINCT FROM %s)",
                (location["longitude"], location["latitude"], seat["municipality_teryt"], Jsonb(seat["address"]),
                 seat["verified_on"], seat["source_key"], Jsonb(seat["address"]),
                 location["longitude"], location["latitude"], seat["municipality_teryt"], Jsonb(seat["address"])),
            ).rowcount
    return changed
