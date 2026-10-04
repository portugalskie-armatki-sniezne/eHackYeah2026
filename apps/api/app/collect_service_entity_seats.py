"""collect a reviewable seat snapshot without changing the database."""

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import psycopg
from psycopg.rows import dict_row

from app import geocoding, municipalities
from app.common import Location
from app.db import conninfo


def collect_seats(
    connection: psycopg.Connection, entities: list[dict], reviews: list[dict], verified_on: str
) -> list[dict]:
    reviewed = {review["source_key"]: review for review in reviews}
    if len(reviewed) != len(reviews) or set(reviewed) - {e["source_key"] for e in entities}:
        raise ValueError("Duplicate or unknown seat review identity")
    seats = []
    for entity in entities:
        address = [entity["locality"], entity["street"], entity["house_number"]]
        review = reviewed.get(entity["source_key"], {})
        if review and review["address"] != address:
            raise ValueError(f"Seat review address changed: {entity['source_key']}")
        lookup = review.get("lookup_address", address)
        street = geocoding.normalized_street(lookup[1])
        query_address = f"{lookup[0]}, {street} {lookup[2]}" if street else f"{lookup[0]} {lookup[2]}"
        query = urlencode({"request": "GetAddress", "address": query_address, "accuracy": "0.8", "exact_number": "1"})
        sources = sorted(set(entity["source_urls"] + review.get("source_urls", []) + [f"{geocoding.UUG_URL}?{query}"]))
        location = None
        if "location" in review:
            location = Location.model_validate(review["location"])
        elif lookup[0] and lookup[2]:
            point = geocoding.address_point(*lookup, entity["postal_code"])
            if point:
                coordinates = connection.execute(
                    "SELECT ST_X(p) AS longitude, ST_Y(p) AS latitude FROM "
                    "(SELECT ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 2180), 4326) p) s",
                    (point.x, point.y),
                ).fetchone()
                location = Location(**coordinates)
        region = municipalities.resolve_municipality(location) if location else None
        if location and not region:
            raise ValueError(f"No municipality for seat: {entity['source_key']}")
        if location:
            query = urlencode(
                {
                    "request": "GetCommuneByXY",
                    "xy": f"{location.longitude},{location.latitude},4326",
                    "result": "teryt,commune,county",
                }
            )
            sources.append(f"{municipalities.ULDK_URL}?{query}")
        seats.append(
            {
                "source_key": entity["source_key"],
                "address": address,
                "location": location.model_dump() if location else None,
                "municipality_teryt": region.teryt if region else None,
                "verified_on": min(verified_on, review.get("verified_on", verified_on)),
                "source_urls": sources,
                "note": review.get(
                    "note",
                    "Exact PRG address point and PRG municipality boundary."
                    if location
                    else "No unique exact address point. No approximate seat was substituted.",
                ),
            }
        )
    return seats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    entities = json.loads(args.catalog.read_text())["entities"]
    reviews = json.loads(args.reviews.read_text())
    # PostGIS only transforms coordinates; this collector never writes database rows.
    with psycopg.connect(conninfo(), row_factory=dict_row) as connection:
        seats = collect_seats(connection, entities, reviews, date.today().isoformat())
    snapshot = {"format_version": 1, "seats": seats}
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Located {sum(s['location'] is not None for s in seats)} of {len(seats)} seats.")


if __name__ == "__main__":
    main()
