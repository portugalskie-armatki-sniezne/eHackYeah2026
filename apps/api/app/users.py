from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from psycopg import errors, sql
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, model_validator

from app.auth import AdminUser, CurrentUser
from app.db import get_connection
from app.models import USER_COLUMNS, Role, User
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

Connection = Annotated[psycopg.Connection, Depends(get_connection)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True)]
Password = Annotated[str, StringConstraints(min_length=8)]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    email: EmailStr
    phone: Phone | None = None
    password: Password


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    password: Password | None = None
    # only an admin can change roles.
    role: Role | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "UserUpdate":
        # only phone is nullable in the database.
        for field in ("first_name", "last_name", "email", "password", "role"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class UserList(BaseModel):
    items: list[User]
    total: int
    limit: int
    offset: int


def email_taken() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Email is already taken")


def user_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "User not found")


def require_self_or_admin(current_user: User, user_id: UUID) -> None:
    # checked before loading the user, so other users' ids are not revealed.
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to access this user")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, connection: Connection) -> User:
    try:
        with connection.transaction():
            row = connection.execute(
                sql.SQL(
                    "INSERT INTO users (first_name, last_name, email, phone, password_hash) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING {}"
                ).format(USER_COLUMNS),
                (body.first_name, body.last_name, body.email, body.phone,
                 hash_password(body.password)),
            ).fetchone()
    except errors.UniqueViolation:
        raise email_taken() from None
    return User.model_validate(row)


@router.get("")
def list_users(
    _: AdminUser,
    connection: Connection,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserList:
    with connection.transaction():
        total = connection.execute("SELECT count(*) AS total FROM users").fetchone()["total"]
        rows = connection.execute(
            sql.SQL("SELECT {} FROM users ORDER BY created_at, id LIMIT %s OFFSET %s").format(USER_COLUMNS),
            (limit, offset),
        ).fetchall()
    return UserList(items=[User.model_validate(row) for row in rows],
                    total=total, limit=limit, offset=offset)


def fetch_user(user_id: UUID, connection: psycopg.Connection) -> User:
    row = connection.execute(
        sql.SQL("SELECT {} FROM users WHERE id = %s").format(USER_COLUMNS), (user_id,)
    ).fetchone()
    if row is None:
        raise user_not_found()
    return User.model_validate(row)


@router.get("/{user_id}")
def get_user(user_id: UUID, current_user: CurrentUser, connection: Connection) -> User:
    require_self_or_admin(current_user, user_id)
    return fetch_user(user_id, connection)


@router.patch("/{user_id}")
def update_user(user_id: UUID, body: UserUpdate, current_user: CurrentUser, connection: Connection) -> User:
    require_self_or_admin(current_user, user_id)
    changes = body.model_dump(exclude_unset=True)
    if "role" in changes and current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an admin can change roles")
    if "password" in changes:
        changes["password_hash"] = hash_password(changes.pop("password"))
    if not changes:
        return fetch_user(user_id, connection)

    assignments = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(column)) for column in changes
    )
    try:
        with connection.transaction():
            row = connection.execute(
                sql.SQL("UPDATE users SET {} WHERE id = %s RETURNING {}").format(assignments, USER_COLUMNS),
                (*changes.values(), user_id),
            ).fetchone()
    except errors.UniqueViolation:
        raise email_taken() from None
    if row is None:
        raise user_not_found()
    return User.model_validate(row)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, current_user: CurrentUser, connection: Connection) -> Response:
    require_self_or_admin(current_user, user_id)
    try:
        with connection.transaction():
            deleted = connection.execute("DELETE FROM users WHERE id = %s", (user_id,)).rowcount
    except errors.ForeignKeyViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "User has reports") from None
    if not deleted:
        raise user_not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
