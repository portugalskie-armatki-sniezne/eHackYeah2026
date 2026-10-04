from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Response, status
from psycopg import sql
from pydantic import BaseModel, computed_field

from app.auth import CurrentUser
from app.common import Connection, Limit, Offset, Page, fetch_page

router = APIRouter(prefix="/notifications", tags=["notifications"])

# What a notification tells its recipient; the page picks its wording and its
# action buttons by the kind.
Kind = Literal[
    "status_inprogress",
    "status_finished",
    "comment",
    "update",
    "photo_proposal",
    "photo_approved",
    "photo_rejected",
]

ProposalState = Literal["pending", "approved", "rejected"]

NOTIFICATION_COLUMNS = sql.SQL(
    "n.id, n.user_id, n.kind, n.master_report_id, n.photo_proposal_id, n.subject, n.detail, "
    "(SELECT p.state FROM master_report_photo_proposals p WHERE p.id = n.photo_proposal_id) "
    "AS photo_proposal_state, "
    "n.read_at, n.created_at"
)
NOTIFICATION_ORDER = sql.SQL("n.created_at DESC, n.id")


class Notification(BaseModel):
    id: UUID
    user_id: UUID
    kind: Kind
    # the case this is about, null once it has been taken off the map.
    master_report_id: UUID | None
    photo_proposal_id: UUID | None
    subject: str
    detail: str | None
    # whether the offered photo still waits for a decision, so the page knows
    # if its approve and reject buttons are still worth showing.
    photo_proposal_state: ProposalState | None
    read_at: datetime | None
    created_at: datetime

    @computed_field
    @property
    def photo_proposal_url(self) -> str | None:
        return f"/photo-proposals/{self.photo_proposal_id}/file" if self.photo_proposal_id else None


def create(
    connection: psycopg.Connection,
    user_ids: Iterable[UUID],
    kind: str,
    *,
    subject: str,
    master_report_id: UUID | None = None,
    photo_proposal_id: UUID | None = None,
    detail: str | None = None,
) -> None:
    """tell every recipient about one thing that happened, in one statement."""
    recipients = list(dict.fromkeys(user_ids))
    if not recipients:
        return
    connection.execute(
        "INSERT INTO notifications (user_id, kind, master_report_id, photo_proposal_id, subject, detail) "
        "SELECT unnest(%s::uuid[]), %s, %s, %s, %s, %s",
        (recipients, kind, master_report_id, photo_proposal_id, subject, detail),
    )


def followers(connection: psycopg.Connection, master_report_id: UUID, exclude: UUID | None = None) -> Sequence[UUID]:
    """everyone who filed a report folded into the case, so it is theirs to follow."""
    rows = connection.execute(
        "SELECT DISTINCT user_id FROM reports WHERE master_report_id = %s AND user_id IS DISTINCT FROM %s",
        (master_report_id, exclude),
    ).fetchall()
    return [row["user_id"] for row in rows]


def author(connection: psycopg.Connection, master_report_id: UUID) -> UUID | None:
    """whoever filed the case first, which is who decides about an offered photo."""
    row = connection.execute(
        "SELECT user_id FROM reports WHERE master_report_id = %s ORDER BY created_at, id LIMIT 1",
        (master_report_id,),
    ).fetchone()
    return row["user_id"] if row else None


def fetch_notification(notification_id: UUID, user_id: UUID, connection: psycopg.Connection) -> Notification:
    row = connection.execute(
        sql.SQL("SELECT {} FROM notifications n WHERE n.id = %s AND n.user_id = %s").format(NOTIFICATION_COLUMNS),
        (notification_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return Notification.model_validate(row)


class UnreadCount(BaseModel):
    count: int


@router.get("")
def list_notifications(
    user: CurrentUser, connection: Connection, unread: bool = False, limit: Limit = 50, offset: Offset = 0
) -> Page[Notification]:
    conditions = [sql.SQL("n.user_id = %(user_id)s")]
    if unread:
        conditions.append(sql.SQL("n.read_at IS NULL"))
    total, rows = fetch_page(
        connection,
        NOTIFICATION_COLUMNS,
        sql.SQL("notifications n"),
        conditions,
        {"user_id": user.id},
        NOTIFICATION_ORDER,
        limit,
        offset,
    )
    return Page[Notification](
        items=[Notification.model_validate(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/unread-count")
def count_unread(user: CurrentUser, connection: Connection) -> UnreadCount:
    row = connection.execute(
        "SELECT count(*) AS count FROM notifications WHERE user_id = %s AND read_at IS NULL", (user.id,)
    ).fetchone()
    return UnreadCount(count=row["count"])


@router.put("/{notification_id}/read")
def mark_read(notification_id: UUID, user: CurrentUser, connection: Connection) -> Notification:
    # idempotent, a second call keeps the first timestamp.
    with connection.transaction():
        connection.execute(
            "UPDATE notifications SET read_at = NOW() WHERE id = %s AND user_id = %s AND read_at IS NULL",
            (notification_id, user.id),
        )
    return fetch_notification(notification_id, user.id, connection)


@router.post("/read-all")
def mark_all_read(user: CurrentUser, connection: Connection) -> UnreadCount:
    with connection.transaction():
        connection.execute(
            "UPDATE notifications SET read_at = NOW() WHERE user_id = %s AND read_at IS NULL", (user.id,)
        )
    return UnreadCount(count=0)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(notification_id: UUID, user: CurrentUser, connection: Connection) -> Response:
    with connection.transaction():
        deleted = connection.execute(
            "DELETE FROM notifications WHERE id = %s AND user_id = %s", (notification_id, user.id)
        ).rowcount
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
