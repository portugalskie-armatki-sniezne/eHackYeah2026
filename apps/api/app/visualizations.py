import hashlib
import json
import math
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, computed_field

from app import storage
from app.auth import CurrentUser, OptionalUser
from app.common import Connection, Limit, Offset, Page, Text
from app.models import User
from app.workflow_settings import settings

router = APIRouter(tags=["visualizations"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
# what the picture shows, by report_categories.name: an improvement carried out, or an issue repaired.
ReportType = Literal["improvement", "issue"]
JOB_COLUMNS = (
    "j.id, j.user_id, j.draft_id, d.report_id, j.report_type, j.status, j.prompt, j.media_type, j.error_code, "
    "j.created_at, j.completed_at, j.storage_key, "
    "(d.report_id IS NOT NULL OR (d.published_at IS NULL AND d.expires_at > statement_timestamp())) AS available"
)


class Visualization(BaseModel):
    id: UUID
    draft_id: UUID | None
    report_id: UUID | None
    report_type: ReportType
    status: Literal["queued", "running", "succeeded", "failed"]
    prompt: str | None
    media_type: str | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None
    generated: Literal[True] = True
    url: str | None


class AcceptedVisualization(Visualization):
    @computed_field
    @property
    def status_url(self) -> str:
        return f"/visualizations/{self.id}"


def result(row: dict, accepted: bool = False) -> Visualization:
    model = AcceptedVisualization if accepted else Visualization
    url = f"/visualizations/{row['id']}/file" if row["storage_key"] and row["available"] else None
    return model.model_validate(row | {"url": url})


def fetch_job(job_id: UUID, connection: psycopg.Connection) -> dict:
    row = connection.execute(
        f"SELECT {JOB_COLUMNS} FROM visualization_jobs j LEFT JOIN visualization_drafts d ON d.id = j.draft_id "
        "WHERE j.id = %s",
        (job_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Visualization not found")
    return row


def require_owner(user: User | None, user_id: UUID) -> None:
    if user is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    if user.role != "admin" and user.id != user_id:
        raise HTTPException(403, "Only the author or an admin can access this visualization")


def validate_photos(photos: list[tuple[str, bytes]]) -> None:
    if not 1 <= len(photos) <= storage.MAX_PHOTOS_PER_REPORT:
        raise HTTPException(422, "A visualization requires 1-5 photos")
    if sum(len(data) for _, data in photos) > 20 * 1024 * 1024:
        raise HTTPException(413, "Photos can have at most 20 MB in total")


def enqueue(
    connection: psycopg.Connection,
    user: User,
    key: str,
    report_type: ReportType,
    description: str,
    photos: list[tuple[str, bytes]],
    *,
    draft_id: UUID | None = None,
    report_id: UUID | None = None,
) -> AcceptedVisualization:
    validate_photos(photos)
    config = settings()
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "draft_id": str(draft_id),
                "report_id": str(report_id),
                "report_type": report_type,
                "description": description,
                "photos": [hashlib.sha256(data).hexdigest() for _, data in photos],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with storage.cleanup_on_error() as saved, connection.transaction():
        connection.execute("SELECT id FROM users WHERE id = %s FOR NO KEY UPDATE", (user.id,))
        previous = connection.execute(
            "SELECT id, request_hash FROM visualization_jobs WHERE user_id = %s AND idempotency_key = %s",
            (user.id, key),
        ).fetchone()
        if previous:
            if previous["request_hash"] != fingerprint:
                raise HTTPException(409, "Idempotency-Key was already used for a different request")
            return result(fetch_job(previous["id"], connection), accepted=True)
        active = connection.execute(
            "SELECT id FROM visualization_jobs WHERE user_id = %s AND status IN ('queued', 'running')", (user.id,)
        ).fetchone()
        if active:
            raise HTTPException(409, {"message": "A visualization is already active", "job_id": str(active["id"])})
        usage = connection.execute(
            "SELECT count(*) AS count, EXTRACT(EPOCH FROM (min(created_at) + %s * interval '1 second' "
            "- statement_timestamp())) AS retry_after FROM visualization_jobs WHERE user_id = %s "
            "AND created_at > statement_timestamp() - %s * interval '1 second'",
            (config.window_seconds, user.id, config.window_seconds),
        ).fetchone()
        if usage["count"] >= config.gemini_user_limit:
            raise HTTPException(
                429,
                "Visualization limit exceeded",
                headers={"Retry-After": str(max(1, math.ceil(usage["retry_after"])))},
            )
        if report_id is not None:
            draft = connection.execute(
                "SELECT id FROM visualization_drafts WHERE report_id = %s FOR UPDATE", (report_id,)
            ).fetchone()
            if draft:
                draft_id = draft["id"]
        if draft_id is None:
            draft_id = connection.execute(
                "INSERT INTO visualization_drafts (user_id, report_id, published_at, expires_at) "
                "VALUES (%s, %s, CASE WHEN %s::uuid IS NULL THEN NULL ELSE statement_timestamp() END, "
                "statement_timestamp() + %s * interval '1 day') RETURNING id",
                (user.id, report_id, report_id, config.draft_ttl_days),
            ).fetchone()["id"]
        else:
            draft = connection.execute(
                "SELECT * FROM visualization_drafts WHERE id = %s FOR UPDATE", (draft_id,)
            ).fetchone()
            if draft is None:
                raise HTTPException(404, "Visualization draft not found")
            if report_id is None:
                require_owner(user, draft["user_id"])
                if draft["published_at"] is not None:
                    raise HTTPException(409, "Use the report endpoint for a published draft")
                expired = connection.execute(
                    "SELECT expires_at <= statement_timestamp() AS expired FROM visualization_drafts WHERE id = %s",
                    (draft_id,),
                ).fetchone()["expired"]
                if expired:
                    raise HTTPException(410, "Visualization draft expired")
        job_id = uuid4()
        keys = []
        for extension, data in photos:
            source_key = f"visualizations/{job_id}/{uuid4()}.{extension}"
            saved.append(source_key)
            storage.save(source_key, data)
            keys.append(source_key)
        connection.execute(
            "INSERT INTO visualization_jobs (id, user_id, draft_id, idempotency_key, request_hash, report_type, "
            "description, source_keys) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (job_id, user.id, draft_id, key, fingerprint, report_type, description, Jsonb(keys)),
        )
        return result(fetch_job(job_id, connection), accepted=True)


@router.post("/visualizations", status_code=status.HTTP_202_ACCEPTED, response_model=AcceptedVisualization)
def generate_draft(
    user: CurrentUser,
    connection: Connection,
    idempotency_key: IdempotencyKey,
    description: Annotated[Text, Form()],
    photos: Annotated[list[UploadFile], File()],
    draft_id: Annotated[UUID | None, Form()] = None,
    report_type: Annotated[ReportType, Form()] = "improvement",
) -> AcceptedVisualization:
    from app.reports import read_photos

    return enqueue(connection, user, idempotency_key, report_type, description, read_photos(photos), draft_id=draft_id)


@router.post("/reports/{report_id}/visualizations", status_code=202, response_model=AcceptedVisualization)
def generate_report(
    report_id: UUID,
    user: CurrentUser,
    connection: Connection,
    idempotency_key: IdempotencyKey,
) -> AcceptedVisualization:
    from app.reports import lock_report, read_saved_photos, require_owner_or_admin

    with connection.transaction():
        # take the user lock first, as in draft generation, before locking the report.
        connection.execute("SELECT id FROM users WHERE id = %s FOR NO KEY UPDATE", (user.id,))
        require_owner_or_admin(user, lock_report(report_id, connection))
        row = connection.execute(
            "SELECT r.description, c.name FROM reports r JOIN report_categories c ON c.id = r.report_category_id "
            "WHERE r.id = %s",
            (report_id,),
        ).fetchone()
        rows = connection.execute(
            "SELECT storage_key FROM report_photos WHERE report_id = %s ORDER BY created_at, id", (report_id,)
        ).fetchall()
        photos = read_saved_photos([row["storage_key"] for row in rows])
        return enqueue(connection, user, idempotency_key, row["name"], row["description"], photos, report_id=report_id)


def attach_draft(
    draft_id: UUID, report_id: UUID, user_id: UUID, category_id: int, connection: psycopg.Connection
) -> None:
    draft = connection.execute("SELECT * FROM visualization_drafts WHERE id = %s FOR UPDATE", (draft_id,)).fetchone()
    if draft is None:
        raise HTTPException(404, "Visualization draft not found")
    if draft["user_id"] != user_id:
        raise HTTPException(403, "Only the draft owner can publish it")
    if draft["published_at"] is not None:
        raise HTTPException(409, "Visualization draft was already published")
    # the draft's pictures were drawn for one kind of report, which the published report must be.
    valid = connection.execute(
        "SELECT d.expires_at > statement_timestamp() AS available, c.name, "
        "(SELECT j.report_type FROM visualization_jobs j WHERE j.draft_id = d.id "
        "ORDER BY j.created_at DESC, j.id DESC LIMIT 1) AS report_type "
        "FROM visualization_drafts d CROSS JOIN report_categories c WHERE d.id = %s AND c.id = %s",
        (draft_id, category_id),
    ).fetchone()
    if valid is None or (valid["report_type"] is not None and valid["report_type"] != valid["name"]):
        raise HTTPException(422, "The visualization draft was made for another report category")
    if not valid["available"]:
        raise HTTPException(410, "Visualization draft expired")
    connection.execute(
        "UPDATE visualization_drafts SET report_id = %s, published_at = statement_timestamp() WHERE id = %s",
        (report_id, draft_id),
    )


@router.get("/visualizations/{job_id}", response_model=Visualization)
def get_visualization(job_id: UUID, user: CurrentUser, connection: Connection) -> Visualization:
    row = fetch_job(job_id, connection)
    require_owner(user, row["user_id"])
    return result(row)


@router.get("/visualizations/{job_id}/file", response_class=FileResponse)
def get_file(job_id: UUID, connection: Connection, user: OptionalUser) -> FileResponse:
    row = fetch_job(job_id, connection)
    if row["report_id"] is None:
        require_owner(user, row["user_id"])
    if not row["available"]:
        raise HTTPException(410, "Visualization is no longer available")
    if row["status"] != "succeeded" or not storage.file_path(row["storage_key"]).is_file():
        raise HTTPException(404, "Visualization file not found")
    return FileResponse(storage.file_path(row["storage_key"]), media_type=row["media_type"])


def history(
    target_id: UUID, master: bool, connection: psycopg.Connection, limit: int, offset: int
) -> Page[Visualization]:
    table = "master_reports" if master else "reports"
    if connection.execute(f"SELECT id FROM {table} WHERE id = %s", (target_id,)).fetchone() is None:
        raise HTTPException(404, "Report not found")
    condition = "r.master_report_id = %s" if master else "r.id = %s"
    source = (
        "FROM visualization_jobs j JOIN visualization_drafts d ON d.id = j.draft_id "
        f"JOIN reports r ON r.id = d.report_id WHERE {condition} AND j.status = 'succeeded'"
    )
    total = connection.execute(f"SELECT count(*) AS count {source}", (target_id,)).fetchone()["count"]
    rows = connection.execute(
        f"SELECT {JOB_COLUMNS} {source} ORDER BY j.completed_at DESC, j.id DESC LIMIT %s OFFSET %s",
        (target_id, limit, offset),
    ).fetchall()
    return Page[Visualization](items=[result(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/reports/{report_id}/visualizations")
def report_history(
    report_id: UUID, connection: Connection, limit: Limit = 50, offset: Offset = 0
) -> Page[Visualization]:
    return history(report_id, False, connection, limit, offset)


@router.get("/master-reports/{master_id}/visualizations")
def master_history(
    master_id: UUID, connection: Connection, limit: Limit = 50, offset: Offset = 0
) -> Page[Visualization]:
    return history(master_id, True, connection, limit, offset)
