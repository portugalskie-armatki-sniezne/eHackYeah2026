"""validate and upsert the ROPS social innovation snapshot."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import TYPE_CHECKING

from import_service_entities import http_url

if TYPE_CHECKING:
    import psycopg


COLUMNS = (
    "slug", "title", "category", "category_slug", "url", "summary",
    "description", "problem", "target_group", "beneficiaries", "effectiveness", "authors",
)
REQUIRED = ("slug", "title", "category", "url", "summary")
# the texts of an innovation that become its searchable chunks, in page order
CHUNK_COLUMNS = ("summary", "description", "problem", "target_group", "beneficiaries", "effectiveness")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def validate_projects(records: list[dict]) -> list[dict]:
    if not isinstance(records, list) or not records:
        raise ValueError("Expected a nonempty project list")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != set(COLUMNS):
            raise ValueError("Unexpected project fields")
        for column in COLUMNS:
            value = record[column]
            if value is None:
                if column in REQUIRED:
                    raise ValueError(f"Missing project field: {column}")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid project field: {column}")
        slug = record["slug"]
        if not SLUG.fullmatch(slug) or slug in seen:
            raise ValueError(f"Missing or duplicate project slug: {slug}")
        seen.add(slug)
        if record["category_slug"] is not None and not SLUG.fullmatch(record["category_slug"]):
            raise ValueError(f"Invalid category slug: {slug}")
        if not http_url(record["url"]):
            raise ValueError(f"Invalid project URL: {slug}")
    return records


def read_projects(path: Path) -> list[dict]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if snapshot.get("format_version") != 1:
        raise ValueError("Unsupported project snapshot format")
    return validate_projects(snapshot["projects"])


def chunks_of(record: dict) -> list[str]:
    return [record[column] for column in CHUNK_COLUMNS if record[column]]


def import_projects(connection: psycopg.Connection, records: list[dict]) -> int:
    from psycopg import sql

    validate_projects(records)
    columns = sql.SQL(", ").join(map(sql.Identifier, COLUMNS))
    assignments = sql.SQL(", ").join(
        sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(column)) for column in COLUMNS[1:]
    )
    current = sql.SQL(", ").join(sql.Identifier("projects", column) for column in COLUMNS[1:])
    new = sql.SQL(", ").join(sql.Identifier("excluded", column) for column in COLUMNS[1:])
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('projects_seed', 0))")
        cursor.execute(sql.SQL(
            "CREATE TEMP TABLE staged_projects ON COMMIT DROP AS "
            "SELECT {} FROM projects WITH NO DATA"
        ).format(columns))
        with cursor.copy(sql.SQL("COPY staged_projects ({}) FROM STDIN").format(columns)) as copy:
            for record in records:
                copy.write_row([record[column] for column in COLUMNS])
        cursor.execute(sql.SQL(
            "INSERT INTO projects ({columns}) SELECT {columns} FROM staged_projects "
            "ON CONFLICT (slug) DO UPDATE SET {assignments} "
            "WHERE ({current}) IS DISTINCT FROM ({new})"
        ).format(columns=columns, assignments=assignments, current=current, new=new))
        changes = cursor.rowcount
        # the chunks are derived from the snapshot, so the listed projects get theirs written afresh
        cursor.execute("DELETE FROM project_chunks WHERE project_slug = ANY(%s)",
                       ([record["slug"] for record in records],))
        with cursor.copy("COPY project_chunks (project_slug, chunk_index, source_file, content) FROM STDIN") as copy:
            for record in records:
                for index, content in enumerate(chunks_of(record)):
                    copy.write_row([record["slug"], index, record["url"], content])
        return changes
