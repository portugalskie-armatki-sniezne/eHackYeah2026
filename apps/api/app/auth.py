from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from psycopg import sql
from pydantic import BaseModel

from app.db import get_connection
from app.models import USER_COLUMNS, User, normalize_phone
from app.security import create_access_token, read_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
Connection = Annotated[psycopg.Connection, Depends(get_connection)]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail,
                         headers={"WWW-Authenticate": "Bearer"})


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], connection: Connection) -> User:
    user_id = read_access_token(token)
    row = None
    if user_id is not None:
        row = connection.execute(
            sql.SQL("SELECT {} FROM users WHERE id = %s").format(USER_COLUMNS), (user_id,)
        ).fetchone()
    # the user is loaded on every request, so role changes and deletions apply immediately.
    if row is None:
        raise unauthorized("Invalid or expired token")
    return User.model_validate(row)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


@router.post("/login")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], connection: Connection) -> Token:
    # OAuth2 calls the login field username, it holds an email or a phone number.
    if "@" in form.username:
        query, login_value = "SELECT id, password_hash FROM users WHERE email = %s", form.username
    else:
        query, login_value = "SELECT id, password_hash FROM users WHERE phone = %s", normalize_phone(form.username)
    row = connection.execute(query, (login_value,)).fetchone()
    if not verify_password(form.password, row["password_hash"] if row else None):
        raise unauthorized("Incorrect login or password")
    return Token(access_token=create_access_token(row["id"]))


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user
