"""validate and upsert the official service entity snapshot."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    import psycopg


COLUMNS = (
    "source_key", "name", "short_name", "entity_type", "teryt_code", "locality",
    "postal_code", "street", "house_number", "phone_number", "email", "website",
    "bip_url", "reporting_channel", "reporting_channel_description", "source_urls", "verified_on", "is_active",
)
ENTITY_TYPES = {
    "road_manager", "transport_authority", "transport_operator", "green_space_manager",
    "water_infrastructure_manager", "water_sewage_utility", "water_sewage_authority", "heating_utility",
    "waste_management", "municipal_services", "municipal_guard", "housing_manager",
    "cemetery_manager", "sports_infrastructure_manager", "municipal_investment",
}


def http_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme in ("https", "http") and bool(parts.hostname) and not parts.username


def validate_entities(records: list[dict]) -> list[dict]:
    if not isinstance(records, list) or not records:
        raise ValueError("Expected a nonempty service entity list")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != set(COLUMNS):
            raise ValueError("Unexpected service entity fields")
        if not isinstance(record["is_active"], bool):
            raise ValueError("Invalid institution activity flag")
        for column in set(COLUMNS) - {"source_urls", "is_active"}:
            value = record[column]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"Invalid service entity field: {column}")
        key = record["source_key"]
        if not key or key in seen or not record["name"]:
            raise ValueError("Missing or duplicate service entity identity")
        seen.add(key)
        if record["entity_type"] not in ENTITY_TYPES:
            raise ValueError(f"Unknown entity type: {key}")
        if record["teryt_code"] is not None and not re.fullmatch(r"[0-9]{7}", record["teryt_code"]):
            raise ValueError(f"Invalid TERYT code: {key}")
        sources = record["source_urls"]
        if (not isinstance(sources, list) or not sources
                or any(not isinstance(url, str) or not http_url(url) for url in sources)):
            raise ValueError(f"Missing or invalid sources: {key}")
        for column in ("website", "bip_url"):
            if record[column] is not None and not http_url(record[column]):
                raise ValueError(f"Invalid {column}: {key}")
        channel = record["reporting_channel"]
        if channel and not (http_url(channel) or re.fullmatch(r"tel:\+?[0-9]+", channel)
                            or re.fullmatch(r"mailto:[^\s@]+@[^\s@]+\.[^\s@]+", channel)):
            raise ValueError(f"Invalid reporting channel: {key}")
        if not record["verified_on"] or date.fromisoformat(record["verified_on"]) > date.today():
            raise ValueError(f"Invalid verification date: {key}")
    return records


def read_entities(path: Path) -> list[dict]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if snapshot.get("format_version") != 1:
        raise ValueError("Unsupported service entity snapshot format")
    return validate_entities(snapshot["entities"])


def import_entities(connection: psycopg.Connection, records: list[dict]) -> int:
    from psycopg import sql

    validate_entities(records)
    columns = sql.SQL(", ").join(map(sql.Identifier, COLUMNS))
    assignments = sql.SQL(", ").join(
        sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(column)) for column in COLUMNS[1:]
    )
    current = sql.SQL(", ").join(sql.Identifier("service_entities", column) for column in COLUMNS[1:])
    new = sql.SQL(", ").join(sql.Identifier("excluded", column) for column in COLUMNS[1:])
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('service_entities_seed', 0))")
        cursor.execute(sql.SQL(
            "CREATE TEMP TABLE staged_entities ON COMMIT DROP AS "
            "SELECT {} FROM service_entities WITH NO DATA"
        ).format(columns))
        with cursor.copy(sql.SQL("COPY staged_entities ({}) FROM STDIN").format(columns)) as copy:
            for record in records:
                copy.write_row([record[column] for column in COLUMNS])
        cursor.execute(sql.SQL(
            "INSERT INTO service_entities ({columns}) SELECT {columns} FROM staged_entities "
            "ON CONFLICT (source_key) DO UPDATE SET {assignments} "
            "WHERE ({current}) IS DISTINCT FROM ({new})"
        ).format(columns=columns, assignments=assignments, current=current, new=new))
        return cursor.rowcount
