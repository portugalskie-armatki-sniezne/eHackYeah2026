from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from psycopg import errors, sql
from pydantic import BaseModel, computed_field

from app import notifications, storage
from app.auth import CurrentUser
from app.common import Connection, Limit, Offset, Page, fetch_page
from app.models import User
from app.notifications import ProposalState
from app.reports import read_photos

router = APIRouter(tags=["photo proposals"])

PROPOSAL_COLUMNS = "p.id, p.master_report_id, p.user_id, p.storage_key, p.state, p.decided_at, p.created_at"
PROPOSAL_ORDER = "p.created_at, p.id"


def proposal_file_url(proposal_id: UUID) -> str:
    # relative to the API base URL and public, like a report photo's own file.
    return f"/photo-proposals/{proposal_id}/file"


class PhotoProposal(BaseModel):
    id: UUID
    master_report_id: UUID
    user_id: UUID
    storage_key: str
    state: ProposalState
    # when the case's author took or turned the photo down, null while it waits.
    decided_at: datetime | None
    created_at: datetime

    @computed_field
    @property
    def url(self) -> str:
        return proposal_file_url(self.id)


def proposal_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Photo proposal not found")


def fetch_proposal(proposal_id: UUID, connection: psycopg.Connection) -> PhotoProposal:
    row = connection.execute(
        f"SELECT {PROPOSAL_COLUMNS} FROM master_report_photo_proposals p WHERE p.id = %s", (proposal_id,)
    ).fetchone()
    if row is None:
        raise proposal_not_found()
    return PhotoProposal.model_validate(row)


def lock_pending(proposal_id: UUID, user: User, connection: psycopg.Connection) -> dict[str, Any]:
    """take the waiting proposal and check the caller is the one who decides about it."""
    row = connection.execute(
        f"SELECT {PROPOSAL_COLUMNS} FROM master_report_photo_proposals p WHERE p.id = %s FOR UPDATE",
        (proposal_id,),
    ).fetchone()
    if row is None:
        raise proposal_not_found()
    if row["state"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This photo has already been decided on")
    if user.role != "admin" and user.id != notifications.author(connection, row["master_report_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the resident who filed the case can decide on its photo")
    return row


def master_title(master_report_id: UUID, connection: psycopg.Connection) -> str:
    row = connection.execute("SELECT title FROM master_reports WHERE id = %s", (master_report_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Master report not found")
    return row["title"]


def take_photo(master_report_id: UUID, storage_key: str, connection: psycopg.Connection) -> str:
    """file the offered photo under the case's first report, where the map reads it from."""
    report = connection.execute(
        "SELECT id FROM reports WHERE master_report_id = %s ORDER BY created_at, id LIMIT 1",
        (master_report_id,),
    ).fetchone()
    if report is None:
        # the case lost its last report while the photo waited.
        raise HTTPException(status.HTTP_409_CONFLICT, "The case has no report left to attach the photo to")
    photo_id = uuid4()
    extension = storage_key.rsplit(".", 1)[-1]
    photo_key = f"reports/{report['id']}/{photo_id}.{extension}"
    connection.execute(
        "INSERT INTO report_photos (id, report_id, storage_key) VALUES (%s, %s, %s)",
        (photo_id, report["id"], photo_key),
    )
    storage.move(storage_key, photo_key)
    return photo_key


def decide(proposal_id: UUID, state: str, connection: psycopg.Connection) -> None:
    connection.execute(
        "UPDATE master_report_photo_proposals SET state = %s, decided_at = NOW() WHERE id = %s",
        (state, proposal_id),
    )


@router.post("/master-reports/{master_report_id}/photo-proposals", status_code=status.HTTP_201_CREATED)
def offer_photo(
    master_report_id: UUID,
    user: CurrentUser,
    connection: Connection,
    photo: Annotated[UploadFile, File(description="one JPEG, PNG, or WebP image, 10 MB at most")],
) -> PhotoProposal:
    """Offer a photo for a case that has none. Whoever filed the case decides whether it stays."""
    extension, data = read_photos([photo])[0]
    proposal_id = uuid4()
    storage_key = f"proposals/{proposal_id}.{extension}"
    try:
        with storage.cleanup_on_error() as saved, connection.transaction():
            title = master_title(master_report_id, connection)
            if connection.execute(
                "SELECT 1 FROM report_photos p JOIN reports r ON r.id = p.report_id WHERE r.master_report_id = %s",
                (master_report_id,),
            ).fetchone():
                raise HTTPException(status.HTTP_409_CONFLICT, "This case already has a photo")
            connection.execute(
                "INSERT INTO master_report_photo_proposals (id, master_report_id, user_id, storage_key) "
                "VALUES (%s, %s, %s, %s)",
                (proposal_id, master_report_id, user.id, storage_key),
            )
            storage.save(storage_key, data)
            saved.append(storage_key)
            author = notifications.author(connection, master_report_id)
            if author == user.id:
                # the resident who filed the case needs nobody's leave for their own photo.
                saved.append(take_photo(master_report_id, storage_key, connection))
                decide(proposal_id, "approved", connection)
            else:
                notifications.create(
                    connection,
                    [author] if author else [],
                    "photo_proposal",
                    subject=title,
                    master_report_id=master_report_id,
                    photo_proposal_id=proposal_id,
                )
    except errors.UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "Another photo is already waiting for this case") from None
    return fetch_proposal(proposal_id, connection)


@router.get("/master-reports/{master_report_id}/photo-proposals")
def list_photo_proposals(
    master_report_id: UUID,
    connection: Connection,
    state: ProposalState | None = "pending",
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[PhotoProposal]:
    conditions = [sql.SQL("p.master_report_id = %(master_report_id)s")]
    params: dict[str, Any] = {"master_report_id": master_report_id}
    if state is not None:
        conditions.append(sql.SQL("p.state = %(state)s"))
        params["state"] = state
    total, rows = fetch_page(
        connection,
        sql.SQL(PROPOSAL_COLUMNS),
        sql.SQL("master_report_photo_proposals p"),
        conditions,
        params,
        sql.SQL(PROPOSAL_ORDER),
        limit,
        offset,
    )
    return Page[PhotoProposal](
        items=[PhotoProposal.model_validate(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/photo-proposals/{proposal_id}/file", response_class=FileResponse)
def get_proposal_file(proposal_id: UUID, connection: Connection) -> FileResponse:
    row = connection.execute(
        "SELECT storage_key FROM master_report_photo_proposals WHERE id = %s", (proposal_id,)
    ).fetchone()
    path = storage.file_path(row["storage_key"]) if row else None
    if path is None or not path.is_file():
        raise proposal_not_found()
    return FileResponse(path, media_type=storage.media_type(row["storage_key"]))


@router.post("/photo-proposals/{proposal_id}/approve")
def approve_photo(proposal_id: UUID, user: CurrentUser, connection: Connection) -> PhotoProposal:
    """Take the offered photo: it becomes the case's photo and loses its question mark."""
    with connection.transaction():
        proposal = lock_pending(proposal_id, user, connection)
        take_photo(proposal["master_report_id"], proposal["storage_key"], connection)
        decide(proposal_id, "approved", connection)
        notifications.create(
            connection,
            [proposal["user_id"]],
            "photo_approved",
            subject=master_title(proposal["master_report_id"], connection),
            master_report_id=proposal["master_report_id"],
            photo_proposal_id=proposal_id,
        )
    return fetch_proposal(proposal_id, connection)


@router.post("/photo-proposals/{proposal_id}/reject")
def reject_photo(proposal_id: UUID, user: CurrentUser, connection: Connection) -> PhotoProposal:
    """Turn the offered photo down: the file goes and the case stays without one."""
    with connection.transaction():
        proposal = lock_pending(proposal_id, user, connection)
        decide(proposal_id, "rejected", connection)
        notifications.create(
            connection,
            [proposal["user_id"]],
            "photo_rejected",
            subject=master_title(proposal["master_report_id"], connection),
            master_report_id=proposal["master_report_id"],
            photo_proposal_id=proposal_id,
        )
    storage.delete([proposal["storage_key"]])
    return fetch_proposal(proposal_id, connection)
