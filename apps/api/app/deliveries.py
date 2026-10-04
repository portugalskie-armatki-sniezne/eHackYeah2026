from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from app.auth import CurrentUser
from app.common import Connection, location_json
from app.models import User

router = APIRouter(tags=["deliveries"])


class Delivery(BaseModel):
    id: UUID
    master_report_id: UUID | None
    status: str
    mock: bool
    error_code: str | None
    next_attempt_at: datetime
    dispatched_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


def enqueue(connection: psycopg.Connection, master_id: UUID, report_id: UUID, user: User) -> None:
    from psycopg import sql

    master = connection.execute(
        sql.SQL(
            "SELECT m.title, m.description, c.name, {} AS location FROM master_reports m "
            "JOIN report_categories c ON c.id = m.report_category_id WHERE m.id = %s"
        ).format(location_json("m")),
        (master_id,),
    ).fetchone()
    photos = connection.execute(
        "SELECT storage_key FROM report_photos WHERE report_id = %s ORDER BY created_at, id", (report_id,)
    ).fetchall()
    generation = connection.execute(
        "SELECT j.id FROM visualization_jobs j JOIN visualization_drafts d ON d.id = j.draft_id "
        "WHERE d.report_id = %s ORDER BY j.created_at DESC, j.id DESC LIMIT 1",
        (report_id,),
    ).fetchone()
    payload = {
        "subject": master["title"],
        "description": master["description"],
        "report_type": master["name"],
        "first_name": user.first_name or None,
        "last_name": user.last_name or None,
        "anonymous": not (user.first_name and user.last_name),
        "location": master["location"],
        "photos": photos,
    }
    connection.execute(
        "INSERT INTO mail_delivery_jobs (user_id, master_report_id, visualization_job_id, payload) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (master_report_id) DO NOTHING",
        (user.id, master_id, generation["id"] if generation else None, Jsonb(payload)),
    )


@router.get("/master-reports/{master_id}/delivery", response_model=Delivery)
def get_delivery(master_id: UUID, user: CurrentUser, connection: Connection) -> Delivery:
    row = connection.execute("SELECT * FROM mail_delivery_jobs WHERE master_report_id = %s", (master_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Delivery not found")
    if user.role != "admin" and user.id != row["user_id"]:
        raise HTTPException(403, "Only the author or an admin can access this delivery")
    return Delivery.model_validate(row)
