from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from psycopg import errors, sql
from pydantic import BaseModel

from app.db import get_connection
from app.models import USER_COLUMNS, User, normalize_phone
from app.security import (
    GoogleUnavailableError,
    create_access_token,
    google_client_id,
    read_access_token,
    read_google_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
# public endpoints accept a token to personalize the response, for example liked_by_me.
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)
Connection = Annotated[psycopg.Connection, Depends(get_connection)]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GoogleCredential(BaseModel):
    # the ID token that Google issued to the client.
    credential: str


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


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


def get_optional_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)], connection: Connection
) -> User | None:
    return None if token is None else get_current_user(token, connection)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_staff(user: CurrentUser) -> User:
    if user.role not in ("office", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Office or admin role required")
    return user


StaffUser = Annotated[User, Depends(require_staff)]


def google_claims(credential: str) -> dict | None:
    client_id = google_client_id()
    if client_id is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured")
    try:
        return read_google_token(credential, client_id)
    except GoogleUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is unavailable") from None


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


@router.post("/google")
def google_login(body: GoogleCredential, connection: Connection) -> Token:
    claims = google_claims(body.credential)
    if claims is None:
        raise unauthorized("Invalid Google token")
    by_google_sub = "SELECT id FROM users WHERE google_sub = %s"
    row = connection.execute(by_google_sub, (claims["sub"],)).fetchone()
    if row is None:
        email = claims.get("email")
        if not email or claims.get("email_verified") is not True:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Google account has no verified email")
        # an existing account is never linked here, only its signed-in owner can link it.
        email_taken = HTTPException(
            status.HTTP_409_CONFLICT,
            "An account with this email already exists, sign in to it and link Google in the profile settings",
        )
        if connection.execute("SELECT 1 FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone():
            raise email_taken
        try:
            with connection.transaction():
                row = connection.execute(
                    "INSERT INTO users (first_name, last_name, email, google_sub) VALUES (%s, %s, %s, %s) RETURNING id",
                    (
                        # Google does not always send both names.
                        claims.get("given_name") or claims.get("name") or email.split("@")[0],
                        claims.get("family_name") or "",
                        email,
                        claims["sub"],
                    ),
                ).fetchone()
        except errors.UniqueViolation as error:
            if error.diag.constraint_name != "users_google_sub_key":
                raise email_taken from None
            # a concurrent first sign-in created the account.
            row = connection.execute(by_google_sub, (claims["sub"],)).fetchone()
    return Token(access_token=create_access_token(row["id"]))


@router.post("/google/link")
def link_google(body: GoogleCredential, user: CurrentUser, connection: Connection) -> User:
    claims = google_claims(body.credential)
    if claims is None:
        # not 401, the session is valid and only the Google token is wrong.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Google token")
    try:
        with connection.transaction():
            row = connection.execute(
                sql.SQL("UPDATE users SET google_sub = %s WHERE id = %s RETURNING {}").format(USER_COLUMNS),
                (claims["sub"], user.id),
            ).fetchone()
    except errors.UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "Google account is already linked to another account") from None
    return User.model_validate(row)


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user
