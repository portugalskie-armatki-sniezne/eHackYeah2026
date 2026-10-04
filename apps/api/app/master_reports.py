from datetime import datetime
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from psycopg import errors, sql
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app import notifications, storage
from app.auth import AdminUser, CurrentUser, StaffUser
from app.common import (
    Connection,
    Limit,
    Location,
    NearFilter,
    Offset,
    Page,
    Text,
    assignments,
    fetch_page,
    foreign_key_error,
    location_json,
    reject_nulls,
)
from app.photo_proposals import proposal_file_url
from app.photos import PHOTO_COLUMNS, PHOTO_ORDER, Photo, photo_file_url
from app.reports import Report, fetch_report, read_photos, save_photos

router = APIRouter(prefix="/master-reports", tags=["master reports"])

MASTER_REPORT_COLUMNS = sql.SQL(
    "m.id, m.report_category_id, m.status_id, m.responsible_office_id, m.responsible_service_entity_id, "
    "m.title, m.description, "
    "{location} AS location, m.response, "
    "(SELECT count(*) FROM reports r WHERE r.master_report_id = m.id) AS report_count, "
    "(SELECT p.id FROM report_photos p JOIN reports r ON r.id = p.report_id "
    f"WHERE r.master_report_id = m.id ORDER BY {PHOTO_ORDER} LIMIT 1) AS photo_id, "
    "(SELECT pp.id FROM master_report_photo_proposals pp "
    "WHERE pp.master_report_id = m.id AND pp.state = 'pending' LIMIT 1) AS pending_photo_id, "
    "(SELECT r.user_id FROM reports r WHERE r.master_report_id = m.id "
    "ORDER BY r.created_at, r.id LIMIT 1) AS author_id, "
    "m.edited_at, m.created_at"
).format(location=location_json("m"))

# the status changes a case's residents hear about, by master_report_statuses.name
STATUS_NOTICES = {"inprogress": "status_inprogress", "finished": "status_finished"}

FOREIGN_KEY_ERRORS = {
    "master_reports_report_category_id_fkey": "Report category not found",
    "master_reports_status_id_fkey": "Status not found",
    "master_reports_responsible_office_id_fkey": "Office not found",
    "master_reports_responsible_service_entity_id_fkey": "Service entity not found",
}
ONE_RESPONSIBLE_PARTY = "Set responsible_office_id or responsible_service_entity_id, not both"


class MasterReport(BaseModel):
    id: UUID
    report_category_id: int
    status_id: int
    # at most one responsible party is set.
    responsible_office_id: int | None
    responsible_service_entity_id: int | None
    title: str
    description: str
    location: Location
    response: str | None
    report_count: int
    # whoever filed the case first, who decides about a photo offered for it;
    # null for a master whose last report is gone.
    author_id: UUID | None
    # the earliest photo among the master's reports, which the map shows on the pin
    # without fetching every master's detail; the list carries it as photo_url only.
    photo_id: UUID | None = Field(exclude=True)
    # a photo a resident offered for a case that has none, which the map and the
    # case's sheet show under a question mark until its author decides about it.
    pending_photo_id: UUID | None
    edited_at: datetime
    created_at: datetime

    @computed_field
    @property
    def photo_url(self) -> str | None:
        return photo_file_url(self.photo_id) if self.photo_id else None

    @computed_field
    @property
    def pending_photo_url(self) -> str | None:
        return proposal_file_url(self.pending_photo_id) if self.pending_photo_id else None


class MasterReportDetail(MasterReport):
    # photos of all reports attached to the master.
    photos: list[Photo]


class MasterReportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_category_id: int | None = None
    status_id: int | None = None
    responsible_office_id: int | None = None
    responsible_service_entity_id: int | None = None
    title: Text | None = None
    description: Text | None = None
    location: Location | None = None
    response: Text | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "MasterReportUpdate":
        # the responsible party ids and response can be cleared with null.
        reject_nulls(self, ("report_category_id", "status_id", "title", "description", "location"))
        if self.responsible_office_id is not None and self.responsible_service_entity_id is not None:
            raise ValueError(ONE_RESPONSIBLE_PARTY)
        return self


def master_report_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Master report not found")


def announce_changes(
    connection: psycopg.Connection, master_report_id: UUID, before: dict[str, object], changes: dict[str, object]
) -> None:
    """tell everyone who filed the case what an office just changed on it."""
    status_id = changes.get("status_id")
    kind = None
    if status_id is not None and status_id != before["status_id"]:
        row = connection.execute("SELECT name FROM master_report_statuses WHERE id = %s", (status_id,)).fetchone()
        kind = STATUS_NOTICES.get(row["name"] if row else "")
    if kind is None and changes.keys() - {"status_id"}:
        # anything else an office touched is an update to the case.
        kind = "update"
    if kind is None:
        return
    notifications.create(
        connection,
        notifications.followers(connection, master_report_id),
        kind,
        subject=str(changes.get("title") or before["title"]),
        master_report_id=master_report_id,
        detail=changes.get("response") if isinstance(changes.get("response"), str) else None,
    )


def fetch_master_report(master_report_id: UUID, connection: psycopg.Connection) -> MasterReportDetail:
    with connection.transaction():
        row = connection.execute(
            sql.SQL("SELECT {} FROM master_reports m WHERE m.id = %s").format(MASTER_REPORT_COLUMNS),
            (master_report_id,),
        ).fetchone()
        if row is None:
            raise master_report_not_found()
        photos = connection.execute(
            f"SELECT {PHOTO_COLUMNS} FROM report_photos p JOIN reports r ON r.id = p.report_id "
            f"WHERE r.master_report_id = %s ORDER BY {PHOTO_ORDER}",
            (master_report_id,),
        ).fetchall()
    return MasterReportDetail.model_validate(row | {"photos": photos})


@router.get("")
def list_master_reports(
    connection: Connection,
    near: NearFilter,
    status_id: int | None = None,
    report_category_id: int | None = None,
    responsible_office_id: int | None = None,
    responsible_service_entity_id: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[MasterReport]:
    conditions, params = [], {}
    for column, value in (
        ("status_id", status_id),
        ("report_category_id", report_category_id),
        ("responsible_office_id", responsible_office_id),
        ("responsible_service_entity_id", responsible_service_entity_id),
    ):
        if value is not None:
            conditions.append(sql.SQL("m.{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
            params[column] = value
    if near is not None:
        conditions.append(near.condition("m"))
        params |= near.params()
    total, rows = fetch_page(
        connection,
        MASTER_REPORT_COLUMNS,
        sql.SQL("master_reports m"),
        conditions,
        params,
        sql.SQL("m.created_at DESC, m.id"),
        limit,
        offset,
    )
    return Page[MasterReport](
        items=[MasterReport.model_validate(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{master_report_id}")
def get_master_report(master_report_id: UUID, connection: Connection) -> MasterReportDetail:
    return fetch_master_report(master_report_id, connection)


@router.post("/{master_report_id}/photos", status_code=status.HTTP_201_CREATED)
def add_master_report_photo(
    master_report_id: UUID,
    user: CurrentUser,
    connection: Connection,
    photo: Annotated[UploadFile, File(description="one JPEG, PNG, or WebP image, 10 MB at most")],
) -> Report:
    """attach a photo through a copy of the case's first report owned by the uploader."""
    uploads = read_photos([photo])
    with storage.cleanup_on_error() as saved, connection.transaction():
        master = connection.execute(
            "SELECT id FROM master_reports WHERE id = %s FOR UPDATE", (master_report_id,)
        ).fetchone()
        if master is None:
            raise master_report_not_found()
        report = connection.execute(
            "INSERT INTO reports (user_id, master_report_id, report_category_id, title, description, location, "
            "municipality_teryt, municipality_name, county_teryt, county_name) "
            "SELECT %s, master_report_id, report_category_id, title, description, location, "
            "municipality_teryt, municipality_name, county_teryt, county_name FROM reports "
            "WHERE master_report_id = %s ORDER BY created_at, id LIMIT 1 RETURNING id",
            (user.id, master_report_id),
        ).fetchone()
        if report is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "The case has no report left to copy")
        save_photos(connection, report["id"], uploads, saved)
    return fetch_report(report["id"], connection)


@router.patch("/{master_report_id}")
def update_master_report(
    master_report_id: UUID, body: MasterReportUpdate, _: StaffUser, connection: Connection
) -> MasterReportDetail:
    # status changes are not restricted, office or admin can set any status.
    # changing the responsible party to the other kind needs both ids, one of them null.
    changes = body.model_dump(exclude_unset=True)
    if changes:
        clause, params = assignments(changes)
        try:
            with connection.transaction():
                before = connection.execute(
                    "SELECT status_id, title FROM master_reports WHERE id = %s FOR UPDATE", (master_report_id,)
                ).fetchone()
                if before is None:
                    raise master_report_not_found()
                updated = connection.execute(
                    sql.SQL("UPDATE master_reports SET {} WHERE id = %s").format(clause),
                    (*params, master_report_id),
                ).rowcount
                announce_changes(connection, master_report_id, before, changes)
        except errors.ForeignKeyViolation as error:
            raise foreign_key_error(error, FOREIGN_KEY_ERRORS) from None
        except errors.CheckViolation as error:
            if error.diag.constraint_name != "master_reports_responsible_party_check":
                raise
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, ONE_RESPONSIBLE_PARTY) from None
        if not updated:
            raise master_report_not_found()
    return fetch_master_report(master_report_id, connection)


@router.delete("/{master_report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_report(master_report_id: UUID, _: AdminUser, connection: Connection) -> Response:
    try:
        with connection.transaction():
            deleted = connection.execute("DELETE FROM master_reports WHERE id = %s", (master_report_id,)).rowcount
    except errors.RestrictViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "Master report has reports") from None
    if not deleted:
        raise master_report_not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
