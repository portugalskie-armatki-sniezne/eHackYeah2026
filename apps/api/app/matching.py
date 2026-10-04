"""matching of reports to master reports by place and title, with a model for titles worded differently."""

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from uuid import UUID

import psycopg
from psycopg import sql

from app.common import NAMED_POINT, POINT, Location
from app.inference.masters import MasterMatcher

logger = logging.getLogger(__name__)

MATCH_RADIUS_M = 50
MIN_TITLE_SIMILARITY = 0.5
# the nearest masters offered to the model, so its prompt stays short.
MAX_MODEL_CANDIDATES = 5
# serializes matching and master cleanup, so concurrent reports about one issue get one master.
MATCHING_LOCK_KEY = 20260001


def normalize_title(title: str) -> str:
    # ł has no Unicode decomposition, so it is replaced before removing accents.
    text = unicodedata.normalize("NFKD", title.lower().replace("ł", "l"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def title_similarity(first: str, second: str) -> float:
    return SequenceMatcher(None, normalize_title(first), normalize_title(second)).ratio()


def lock(connection: psycopg.Connection) -> None:
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (MATCHING_LOCK_KEY,))


def candidates(connection: psycopg.Connection, report_category_id: int, location: Location) -> list[dict]:
    """return open masters of the category within the radius, nearest first."""
    return connection.execute(
        sql.SQL(
            "SELECT m.id, m.title, ST_Distance(m.location, {point}) AS distance, "
            "array_remove(array_agg(r.title), NULL) AS report_titles "
            "FROM master_reports m "
            "JOIN master_report_statuses s ON s.id = m.status_id "
            "LEFT JOIN reports r ON r.master_report_id = m.id "
            "WHERE m.report_category_id = %(report_category_id)s AND s.name <> 'finished' "
            "AND ST_DWithin(m.location, {point}, %(radius_m)s) "
            "GROUP BY m.id ORDER BY distance, m.id"
        ).format(point=NAMED_POINT),
        {
            "report_category_id": report_category_id,
            "radius_m": MATCH_RADIUS_M,
            "longitude": location.longitude,
            "latitude": location.latitude,
        },
    ).fetchall()


def best_title_match(rows: list[dict], title: str) -> UUID | None:
    """return the candidate whose title, or a title of its reports, fits best."""
    # the most similar title wins, the nearer master breaks ties.
    matches = [
        (
            max(title_similarity(title, other) for other in [row["title"], *row["report_titles"]]),
            -row["distance"],
            row["id"],
        )
        for row in rows
    ]
    matches = [match for match in matches if match[0] >= MIN_TITLE_SIMILARITY]
    return max(matches)[2] if matches else None


def find_master(connection: psycopg.Connection, report_category_id: int, title: str, location: Location) -> UUID | None:
    """return the open master within the radius whose title, or a title of its reports, fits best."""
    return best_title_match(candidates(connection, report_category_id, location), title)


def suggest_master(
    connection: psycopg.Connection, matcher: MasterMatcher, report_category_id: int, title: str, location: Location
) -> UUID | None:
    """ask the model for an open master nearby when no title is similar, call before taking the matching lock."""
    rows = candidates(connection, report_category_id, location)
    if not rows or best_title_match(rows, title) is not None:
        return None
    try:
        choice = matcher.choose(title, {str(row["id"]): row["title"] for row in rows[:MAX_MODEL_CANDIDATES]})
    except Exception:
        # the report is still saved, matched by titles only.
        logger.warning("Master matching model failed", exc_info=True)
        return None
    return UUID(choice) if choice else None


def create_master(
    connection: psycopg.Connection, report_category_id: int, title: str, description: str, location: Location
) -> UUID:
    return connection.execute(
        sql.SQL(
            "INSERT INTO master_reports (report_category_id, status_id, title, description, location) "
            "SELECT %s, id, %s, %s, {} FROM master_report_statuses WHERE name = 'created' RETURNING id"
        ).format(POINT),
        (report_category_id, title, description, location.longitude, location.latitude),
    ).fetchone()["id"]


def assign_master(
    connection: psycopg.Connection, report_category_id: int, title: str, description: str, location: Location
) -> UUID:
    """find a matching master or create one from the report, call inside a transaction."""
    lock(connection)
    master_id = find_master(connection, report_category_id, title, location)
    return master_id or create_master(connection, report_category_id, title, description, location)


def assign_master_for_publication(
    connection: psycopg.Connection,
    report_category_id: int,
    title: str,
    description: str,
    location: Location,
    suggested_master_id: UUID | None = None,
) -> tuple[UUID, bool]:
    """join a similar master, then the model's suggestion if it is still a candidate, or create a master."""
    lock(connection)
    rows = candidates(connection, report_category_id, location)
    master_id = best_title_match(rows, title)
    if master_id is None and suggested_master_id in {row["id"] for row in rows}:
        master_id = suggested_master_id
    if master_id is not None:
        return master_id, False
    return create_master(connection, report_category_id, title, description, location), True


def delete_if_empty(connection: psycopg.Connection, master_report_id: UUID | None) -> None:
    """delete a master without reports together with its comments, call inside a transaction."""
    if master_report_id is None:
        return
    lock(connection)
    connection.execute(
        "DELETE FROM master_reports m WHERE m.id = %s "
        "AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.master_report_id = m.id)",
        (master_report_id,),
    )
