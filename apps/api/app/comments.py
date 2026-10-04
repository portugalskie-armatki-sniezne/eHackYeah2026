from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Response, status
from psycopg import errors, sql
from pydantic import BaseModel, ConfigDict

from app.auth import CurrentUser, OptionalUser
from app.common import Connection, Limit, Offset, Page, Text, fetch_page

router = APIRouter(tags=["comments"])

COMMENT_COLUMNS = sql.SQL(
    "c.id, c.master_report_id, c.user_id, "
    "(SELECT u.first_name FROM users u WHERE u.id = c.user_id) AS author_first_name, c.content, "
    "(SELECT count(*) FROM master_report_comment_likes l WHERE l.comment_id = c.id) AS like_count, "
    "EXISTS (SELECT 1 FROM master_report_comment_likes l "
    "WHERE l.comment_id = c.id AND l.user_id = %(viewer_id)s) AS liked_by_me, "
    "c.created_at"
)


class Comment(BaseModel):
    id: UUID
    master_report_id: UUID
    user_id: UUID
    author_first_name: str
    content: str
    like_count: int
    # false for anonymous requests.
    liked_by_me: bool
    created_at: datetime


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: Text


def comment_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")


def fetch_comment(comment_id: UUID, viewer_id: UUID | None, connection: psycopg.Connection) -> Comment:
    row = connection.execute(
        sql.SQL("SELECT {} FROM master_report_comments c WHERE c.id = %(comment_id)s").format(COMMENT_COLUMNS),
        {"comment_id": comment_id, "viewer_id": viewer_id},
    ).fetchone()
    if row is None:
        raise comment_not_found()
    return Comment.model_validate(row)


@router.get("/master-reports/{master_report_id}/comments")
def list_comments(
    master_report_id: UUID, user: OptionalUser, connection: Connection, limit: Limit = 50, offset: Offset = 0
) -> Page[Comment]:
    if connection.execute("SELECT 1 FROM master_reports WHERE id = %s", (master_report_id,)).fetchone() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Master report not found")
    total, rows = fetch_page(
        connection,
        COMMENT_COLUMNS,
        sql.SQL("master_report_comments c"),
        [sql.SQL("c.master_report_id = %(master_report_id)s")],
        {"master_report_id": master_report_id, "viewer_id": user.id if user else None},
        sql.SQL("c.created_at, c.id"),
        limit,
        offset,
    )
    return Page[Comment](items=[Comment.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


@router.post("/master-reports/{master_report_id}/comments", status_code=status.HTTP_201_CREATED)
def create_comment(master_report_id: UUID, body: CommentCreate, user: CurrentUser, connection: Connection) -> Comment:
    try:
        with connection.transaction():
            comment_id = connection.execute(
                "INSERT INTO master_report_comments (master_report_id, user_id, content) "
                "VALUES (%s, %s, %s) RETURNING id",
                (master_report_id, user.id, body.content),
            ).fetchone()["id"]
    except errors.ForeignKeyViolation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Master report not found") from None
    return fetch_comment(comment_id, user.id, connection)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: UUID, user: CurrentUser, connection: Connection) -> Response:
    with connection.transaction():
        row = connection.execute(
            "SELECT user_id FROM master_report_comments WHERE id = %s FOR UPDATE", (comment_id,)
        ).fetchone()
        if row is None:
            raise comment_not_found()
        if user.role == "user" and user.id != row["user_id"]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author, office, or admin can delete this comment")
        connection.execute("DELETE FROM master_report_comments WHERE id = %s", (comment_id,))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/comments/{comment_id}/like")
def like_comment(comment_id: UUID, user: CurrentUser, connection: Connection) -> Comment:
    try:
        with connection.transaction():
            connection.execute(
                "INSERT INTO master_report_comment_likes (comment_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (comment_id, user.id),
            )
    except errors.ForeignKeyViolation:
        raise comment_not_found() from None
    return fetch_comment(comment_id, user.id, connection)


@router.delete("/comments/{comment_id}/like")
def unlike_comment(comment_id: UUID, user: CurrentUser, connection: Connection) -> Comment:
    with connection.transaction():
        connection.execute(
            "DELETE FROM master_report_comment_likes WHERE comment_id = %s AND user_id = %s", (comment_id, user.id)
        )
    return fetch_comment(comment_id, user.id, connection)
