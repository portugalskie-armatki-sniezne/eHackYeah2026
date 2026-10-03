from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from psycopg import errors, sql
from pydantic import BaseModel, ConfigDict, model_validator

from app import matching, storage
from app.auth import CurrentUser, StaffUser
from app.common import (
    POINT,
    Connection,
    Latitude,
    Limit,
    Location,
    Longitude,
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
from app.models import User
from app.photos import PHOTO_COLUMNS, PHOTO_ORDER, Photo

router = APIRouter(prefix="/reports", tags=["reports"])

REPORT_COLUMNS = sql.SQL(
    "r.id, r.user_id, r.master_report_id, r.report_category_id, r.title, r.description, "
    "{location} AS location, "
    "COALESCE((SELECT json_agg(json_build_object("
    "'id', p.id, 'report_id', p.report_id, 'storage_key', p.storage_key, 'created_at', p.created_at"
    ") ORDER BY {photo_order}) FROM report_photos p WHERE p.report_id = r.id), '[]'::json) AS photos, "
    "r.edited_at, r.created_at"
).format(location=location_json("r"), photo_order=sql.SQL(PHOTO_ORDER))

FOREIGN_KEY_ERRORS = {
    "reports_report_category_id_fkey": "Report category not found",
    "master_reports_report_category_id_fkey": "Report category not found",
    "reports_master_report_id_fkey": "Master report not found",
}

PhotoUploads = Annotated[
    list[UploadFile] | None,
    File(description="up to 5 JPEG, PNG, or WebP images, 10 MB each"),
]


class Report(BaseModel):
    id: UUID
    user_id: UUID
    master_report_id: UUID | None
    report_category_id: int
    title: str
    description: str
    location: Location
    photos: list[Photo]
    edited_at: datetime
    created_at: datetime


class ReportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_category_id: int | None = None
    title: Text | None = None
    description: Text | None = None
    location: Location | None = None

    @model_validator(mode="after")
    def reject_null_fields(self) -> "ReportUpdate":
        reject_nulls(self, type(self).model_fields)
        return self


class ReportMove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # null moves the report to a new master report created from its content.
    master_report_id: UUID | None


def report_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")


def fetch_report(report_id: UUID, connection: psycopg.Connection) -> Report:
    row = connection.execute(
        sql.SQL("SELECT {} FROM reports r WHERE r.id = %s").format(REPORT_COLUMNS), (report_id,)
    ).fetchone()
    if row is None:
        raise report_not_found()
    return Report.model_validate(row)


def lock_report(report_id: UUID, connection: psycopg.Connection) -> dict[str, Any]:
    row = connection.execute(
        "SELECT id, user_id, master_report_id FROM reports WHERE id = %s FOR UPDATE", (report_id,)
    ).fetchone()
    if row is None:
        raise report_not_found()
    return row


def require_owner_or_admin(user: User, report: dict[str, Any]) -> None:
    if user.role != "admin" and user.id != report["user_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author or an admin can change this report")


def read_photos(files: list[UploadFile], existing: int = 0) -> list[tuple[str, bytes]]:
    """validate uploaded photos and return their extensions and contents."""
    if existing + len(files) > storage.MAX_PHOTOS_PER_REPORT:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"A report can have at most {storage.MAX_PHOTOS_PER_REPORT} photos"
        )
    photos = []
    for file in files:
        data = file.file.read(storage.MAX_PHOTO_BYTES + 1)
        if len(data) > storage.MAX_PHOTO_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "A photo can have at most 10 MB")
        extension = storage.detect_extension(data)
        if extension is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Photos must be JPEG, PNG, or WebP images")
        photos.append((extension, data))
    return photos


def save_photos(
    connection: psycopg.Connection, report_id: UUID, photos: list[tuple[str, bytes]], saved: list[str]
) -> list[UUID]:
    photo_ids = []
    for extension, data in photos:
        photo_id = uuid4()
        storage_key = f"reports/{report_id}/{photo_id}.{extension}"
        connection.execute(
            "INSERT INTO report_photos (id, report_id, storage_key) VALUES (%s, %s, %s)",
            (photo_id, report_id, storage_key),
        )
        storage.save(storage_key, data)
        saved.append(storage_key)
        photo_ids.append(photo_id)
    return photo_ids


@router.post("", status_code=status.HTTP_201_CREATED)
def create_report(
    user: CurrentUser,
    connection: Connection,
    report_category_id: Annotated[int, Form()],
    title: Annotated[Text, Form()],
    description: Annotated[Text, Form()],
    longitude: Annotated[Longitude, Form()],
    latitude: Annotated[Latitude, Form()],
    photos: PhotoUploads = None,
) -> Report:
    uploads = read_photos(photos or [])
    location = Location(longitude=longitude, latitude=latitude)
    try:
        with storage.cleanup_on_error() as saved, connection.transaction():
            # the report joins a similar open master nearby or becomes the first report of a new one.
            master_report_id = matching.assign_master(connection, report_category_id, title, description, location)
            report_id = connection.execute(
                sql.SQL(
                    "INSERT INTO reports (user_id, master_report_id, report_category_id, title, description, location) "
                    "VALUES (%s, %s, %s, %s, %s, {}) RETURNING id"
                ).format(POINT),
                (user.id, master_report_id, report_category_id, title, description, longitude, latitude),
            ).fetchone()["id"]
            save_photos(connection, report_id, uploads, saved)
    except errors.ForeignKeyViolation as error:
        raise foreign_key_error(error, FOREIGN_KEY_ERRORS) from None
    return fetch_report(report_id, connection)


@router.get("")
def list_reports(
    connection: Connection,
    near: NearFilter,
    user_id: UUID | None = None,
    master_report_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[Report]:
    conditions, params = [], {}
    if user_id is not None:
        conditions.append(sql.SQL("r.user_id = %(user_id)s"))
        params["user_id"] = user_id
    if master_report_id is not None:
        conditions.append(sql.SQL("r.master_report_id = %(master_report_id)s"))
        params["master_report_id"] = master_report_id
    if near is not None:
        conditions.append(near.condition("r"))
        params |= near.params()
    total, rows = fetch_page(
        connection,
        REPORT_COLUMNS,
        sql.SQL("reports r"),
        conditions,
        params,
        sql.SQL("r.created_at DESC, r.id"),
        limit,
        offset,
    )
    return Page[Report](items=[Report.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/{report_id}")
def get_report(report_id: UUID, connection: Connection) -> Report:
    return fetch_report(report_id, connection)


@router.patch("/{report_id}")
def update_report(report_id: UUID, body: ReportUpdate, user: CurrentUser, connection: Connection) -> Report:
    # edits do not move the report to another master, office or admin can do it with /move.
    changes = body.model_dump(exclude_unset=True)
    try:
        with connection.transaction():
            require_owner_or_admin(user, lock_report(report_id, connection))
            if changes:
                clause, params = assignments(changes)
                connection.execute(sql.SQL("UPDATE reports SET {} WHERE id = %s").format(clause), (*params, report_id))
    except errors.ForeignKeyViolation as error:
        raise foreign_key_error(error, FOREIGN_KEY_ERRORS) from None
    return fetch_report(report_id, connection)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: UUID, user: CurrentUser, connection: Connection) -> Response:
    with connection.transaction():
        report = lock_report(report_id, connection)
        require_owner_or_admin(user, report)
        storage_keys = [
            row["storage_key"]
            for row in connection.execute(
                "SELECT storage_key FROM report_photos WHERE report_id = %s", (report_id,)
            ).fetchall()
        ]
        connection.execute("DELETE FROM reports WHERE id = %s", (report_id,))
        matching.delete_if_empty(connection, report["master_report_id"])
    storage.delete(storage_keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{report_id}/move")
def move_report(report_id: UUID, body: ReportMove, _: StaffUser, connection: Connection) -> Report:
    try:
        with connection.transaction():
            previous_master_id = lock_report(report_id, connection)["master_report_id"]
            master_report_id = body.master_report_id
            if master_report_id is None:
                report = fetch_report(report_id, connection)
                master_report_id = matching.create_master(
                    connection, report.report_category_id, report.title, report.description, report.location
                )
            if master_report_id != previous_master_id:
                connection.execute(
                    "UPDATE reports SET master_report_id = %s WHERE id = %s", (master_report_id, report_id)
                )
                matching.delete_if_empty(connection, previous_master_id)
    except errors.ForeignKeyViolation as error:
        raise foreign_key_error(error, FOREIGN_KEY_ERRORS) from None
    return fetch_report(report_id, connection)


@router.post("/{report_id}/photos", status_code=status.HTTP_201_CREATED)
def add_photos(
    report_id: UUID,
    user: CurrentUser,
    connection: Connection,
    photos: Annotated[list[UploadFile], File(description="JPEG, PNG, or WebP images, 10 MB each")],
) -> list[Photo]:
    with storage.cleanup_on_error() as saved, connection.transaction():
        require_owner_or_admin(user, lock_report(report_id, connection))
        existing = connection.execute(
            "SELECT count(*) AS count FROM report_photos WHERE report_id = %s", (report_id,)
        ).fetchone()["count"]
        photo_ids = save_photos(connection, report_id, read_photos(photos, existing), saved)
        rows = connection.execute(
            f"SELECT {PHOTO_COLUMNS} FROM report_photos p WHERE p.id = ANY(%s) ORDER BY {PHOTO_ORDER}",
            (photo_ids,),
        ).fetchall()
    return [Photo.model_validate(row) for row in rows]


@router.get("/{report_id}/photos")
def list_photos(report_id: UUID, connection: Connection) -> list[Photo]:
    return fetch_report(report_id, connection).photos


@router.delete("/{report_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(report_id: UUID, photo_id: UUID, user: CurrentUser, connection: Connection) -> Response:
    with connection.transaction():
        require_owner_or_admin(user, lock_report(report_id, connection))
        row = connection.execute(
            "DELETE FROM report_photos WHERE id = %s AND report_id = %s RETURNING storage_key",
            (photo_id, report_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    storage.delete([row["storage_key"]])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
