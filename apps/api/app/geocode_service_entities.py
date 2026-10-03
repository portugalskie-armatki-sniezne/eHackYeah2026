"""persist institution seat coordinates before serving recommendations."""

import argparse
from dataclasses import dataclass

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from app import geocoding, municipalities
from app.common import POINT, Location
from app.db import conninfo


@dataclass
class GeocodingSummary:
    saved: int = 0
    skipped: int = 0
    failed: int = 0


def geocode_entities(connection: psycopg.Connection, refresh: bool = False) -> GeocodingSummary:
    rows = connection.execute(
        "SELECT id, locality, street, house_number FROM service_entities "
        "WHERE %s OR seat_address IS DISTINCT FROM jsonb_build_array(locality, street, house_number) ORDER BY id",
        (refresh,),
    ).fetchall()
    summary = GeocodingSummary()
    for row in rows:
        address = Jsonb([row["locality"], row["street"], row["house_number"]])
        point = None
        region = None
        try:
            if row["locality"] and row["house_number"]:
                point = geocoding.address_point(row["locality"], row["street"], row["house_number"])
            if point is not None:
                coordinates = connection.execute(
                    "SELECT ST_X(seat) AS longitude, ST_Y(seat) AS latitude "
                    "FROM (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 2180), 4326) AS seat) s",
                    (point.x, point.y),
                ).fetchone()
                location = Location(**coordinates)
                region = municipalities.resolve_municipality(location)
        except (geocoding.GeocodingUnavailableError, municipalities.MunicipalityUnavailableError):
            summary.failed += 1
            print(f"Could not geocode service entity {row['id']}; retry the command.", flush=True)
            continue
        if region is None:
            connection.execute(
                "UPDATE service_entities SET seat_location = NULL, seat_teryt = NULL, "
                "seat_geocoded_at = NULL, seat_address = NULL "
                "WHERE id = %s AND jsonb_build_array(locality, street, house_number) = %s",
                (row["id"], address),
            )
            summary.skipped += 1
            continue
        # do not save coordinates if another import changed the address during the lookup.
        updated = connection.execute(
            sql.SQL(
                "UPDATE service_entities SET seat_location = {}, seat_teryt = %s, "
                "seat_geocoded_at = CURRENT_TIMESTAMP, seat_address = %s "
                "WHERE id = %s AND jsonb_build_array(locality, street, house_number) = %s"
            ).format(POINT),
            (location.longitude, location.latitude, region.teryt, address, row["id"], address),
        ).rowcount
        summary.saved += updated
        summary.skipped += 1 - updated
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="also geocode seats already saved for the current address"
    )
    args = parser.parse_args()
    # connection settings come from the environment, as in the API process.
    with psycopg.connect(conninfo(), autocommit=True, row_factory=psycopg.rows.dict_row) as connection:
        result = geocode_entities(connection, refresh=args.refresh)
    print(f"Saved: {result.saved}; skipped: {result.skipped}; failed: {result.failed}.")
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
