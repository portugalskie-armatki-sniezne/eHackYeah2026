import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
# used when the email is unknown so login takes the same time either way.
DUMMY_HASH = password_hash.hash("dummy-password")

TOKEN_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(hours=24)

GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
# the keys are fetched on first use and cached, so the API starts without network access.
google_keys = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=5)


class GoogleUnavailableError(Exception):
    pass


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    if stored_hash is None:
        password_hash.verify(password, DUMMY_HASH)
        return False
    return password_hash.verify(password, stored_hash)


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set, see .env.example")
    return secret


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_LIFETIME}
    return jwt.encode(payload, jwt_secret(), algorithm=TOKEN_ALGORITHM)


def read_access_token(token: str) -> UUID | None:
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[TOKEN_ALGORITHM], options={"require": ["sub", "exp"]})
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


def google_client_id() -> str | None:
    return os.environ.get("GOOGLE_CLIENT_ID") or None


def read_google_token(credential: str, client_id: str) -> dict | None:
    try:
        key = google_keys.get_signing_key_from_jwt(credential)
        return jwt.decode(
            credential,
            key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["sub", "aud", "iss", "exp"]},
        )
    except jwt.PyJWKClientConnectionError as error:
        raise GoogleUnavailableError from error
    except jwt.PyJWTError:
        return None
