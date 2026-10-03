from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Response, status
from psycopg import errors, sql
from pydantic import BaseModel, ConfigDict, model_validator

from app.auth import AdminUser, StaffUser
from app.common import (Connection, Limit, Location, NearFilter, Offset, Page, Text, assignments, fetch_page,
                        foreign_key_error, location_json, reject_nulls)
from app.photos import PHOTO_COLUMNS, PHOTO_ORDER, Photo

router = APIRouter(prefix="/master-reports", tags=["master reports"])

MASTER_REPORT_COLUMNS = sql.SQL(
    "m.id, m.report_category_id, m.status_id, m.responsible_institution_id, m.title, m.description, "
    "{location} AS location, m.response, "
    "(SELECT count(*) FROM reports r WHERE r.master_report_id = m.id) AS report_count, "
    "m.edited_at, m.created_at"
).format(location=location_json("m"))

FOREIGN_KEY_ERRORS = {
    "master_reports_report_category_id_fkey": "Report category not found",
    "master_reports_status_id_fkey": "Status not found",
    "master_reports_responsible_institution_id_fkey": "Institution not found",
}


class MasterReport(BaseModel):
    id: UUID
    report_category_id: int
    status_id: int
    responsible_institution_id: int | None
    title: str
    description: str
    location: Location
    response: str | None
    report_count: int
    edited_at: datetime
    created_at: datetime


class MasterReportDetail(MasterReport):
    # photos of all reports attached to the master.
    photos: list[Photo]


class MasterReportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_category_id: int | None = None
    status_id: int | None = None
    responsible_institution_id: int | None = None
    title: Text | None = None
    description: Text | None = None
    location: Location | None = None
    response: Text | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "MasterReportUpdate":
        # responsible_institution_id and response can be cleared with null.
        reject_nulls(self, ("report_category_id", "status_id", "title", "description", "location"))
        return self


def master_report_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Master report not found")


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
    responsible_institution_id: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[MasterReport]:
    conditions, params = [], {}
    for column, value in (("status_id", status_id), ("report_category_id", report_category_id),
                          ("responsible_institution_id", responsible_institution_id)):
        if value is not None:
            conditions.append(sql.SQL("m.{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
            params[column] = value
    if near is not None:
        conditions.append(near.condition("m"))
        params |= near.params()
    total, rows = fetch_page(connection, MASTER_REPORT_COLUMNS, sql.SQL("master_reports m"), conditions, params,
                             sql.SQL("m.created_at DESC, m.id"), limit, offset)
    return Page[MasterReport](items=[MasterReport.model_validate(row) for row in rows],
                              total=total, limit=limit, offset=offset)


@router.get("/{master_report_id}")
def get_master_report(master_report_id: UUID, connection: Connection) -> MasterReportDetail:
    return fetch_master_report(master_report_id, connection)


@router.patch("/{master_report_id}")
def update_master_report(master_report_id: UUID, body: MasterReportUpdate, _: StaffUser,
                         connection: Connection) -> MasterReportDetail:
    # status changes are not restricted, office or admin can set any status.
    changes = body.model_dump(exclude_unset=True)
    if changes:
        clause, params = assignments(changes)
        try:
            with connection.transaction():
                updated = connection.execute(
                    sql.SQL("UPDATE master_reports SET {} WHERE id = %s").format(clause),
                    (*params, master_report_id),
                ).rowcount
        except errors.ForeignKeyViolation as error:
            raise foreign_key_error(error, FOREIGN_KEY_ERRORS) from None
        if not updated:
            raise master_report_not_found()
    return fetch_master_report(master_report_id, connection)


@router.delete("/{master_report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_report(master_report_id: UUID, _: AdminUser, connection: Connection) -> Response:
    try:
        with connection.transaction():
            deleted = connection.execute("DELETE FROM master_reports WHERE id = %s",
                                         (master_report_id,)).rowcount
    except errors.RestrictViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "Master report has reports") from None
    if not deleted:
        raise master_report_not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
