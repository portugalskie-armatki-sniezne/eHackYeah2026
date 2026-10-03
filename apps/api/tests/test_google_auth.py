from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import security
from conftest import create_user, login

GOOGLE_CLIENT_ID = "test-client.apps.googleusercontent.com"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> None:
    """configure Google sign-in and verify tokens with the test key instead of Google's keys."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=GOOGLE_KEY.public_key()))
    monkeypatch.setattr(security, "google_keys", keys)


def google_token(key: rsa.RSAPrivateKey = GOOGLE_KEY, **overrides: object) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": GOOGLE_CLIENT_ID,
        "sub": uuid4().hex,
        "email": f"jan-{uuid4().hex}@example.com",
        "email_verified": True,
        "given_name": "Jan",
        "family_name": "Kowalski",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    } | overrides
    return jwt.encode({name: value for name, value in claims.items() if value is not None}, key, algorithm="RS256")


def google_login(client: TestClient, **claims: object) -> dict[str, object]:
    response = client.post("/auth/google", json={"credential": google_token(**claims)})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return client.get("/auth/me", headers=headers).json()


@pytest.mark.usefixtures("google")
def test_first_google_login_creates_account(client: TestClient):
    sub, email = uuid4().hex, f"jan-{uuid4().hex}@example.com"

    user = google_login(client, sub=sub, email=email)

    assert user["first_name"] == "Jan" and user["last_name"] == "Kowalski"
    assert user["email"] == email and user["phone"] is None
    assert user["role"] == "user" and user["google_linked"] is True
    # the account is found by the Google id, so a changed Google email does not create another one.
    assert google_login(client, sub=sub, email=f"new-{email}")["id"] == user["id"]
    response = client.post("/auth/login", data={"username": email, "password": "tajne-haslo"})
    assert response.status_code == 401


@pytest.mark.usefixtures("google")
def test_google_login_without_names(client: TestClient):
    email = f"jan-{uuid4().hex}@example.com"

    user = google_login(client, email=email, given_name=None, family_name=None)

    assert user["first_name"] == email.split("@")[0] and user["last_name"] == ""


@pytest.mark.usefixtures("google")
def test_google_login_refuses_existing_email(client: TestClient):
    user = create_user(client)

    for email in (user["email"], user["email"].upper()):
        response = client.post("/auth/google", json={"credential": google_token(email=email)})
        assert response.status_code == 409
    headers = login(client, user["email"])
    assert client.get("/auth/me", headers=headers).json()["google_linked"] is False


@pytest.mark.usefixtures("google")
def test_google_login_rejects_invalid_token(client: TestClient):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    for credential in (
        "not-a-jwt",
        google_token(other_key),
        google_token(aud="another-client.apps.googleusercontent.com"),
        google_token(iss="https://accounts.example.com"),
        google_token(exp=datetime.now(timezone.utc) - timedelta(seconds=1)),
        google_token(sub=None),
    ):
        response = client.post("/auth/google", json={"credential": credential})
        assert response.status_code == 401
    for claims in ({"email_verified": False}, {"email": None}):
        response = client.post("/auth/google", json={"credential": google_token(**claims)})
        assert response.status_code == 403


def test_google_login_requires_configuration(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    response = client.post("/auth/google", json={"credential": google_token()})

    assert response.status_code == 503
    assert response.json()["detail"] == "Google sign-in is not configured"


@pytest.mark.usefixtures("google")
def test_google_login_without_google_keys(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def unreachable(_: str) -> None:
        raise jwt.PyJWKClientConnectionError("unreachable")

    monkeypatch.setattr(security, "google_keys", SimpleNamespace(get_signing_key_from_jwt=unreachable))

    response = client.post("/auth/google", json={"credential": google_token()})

    assert response.status_code == 503
    assert response.json()["detail"] == "Google sign-in is unavailable"


@pytest.mark.usefixtures("google")
def test_link_google_to_password_account(client: TestClient):
    user = create_user(client)
    headers = login(client, user["email"])
    sub = uuid4().hex

    response = client.post("/auth/google/link", json={"credential": google_token(sub=sub)}, headers=headers)

    assert response.status_code == 200
    assert response.json() | {"edited_at": None} == user | {"google_linked": True, "edited_at": None}
    # the Google email differs from the account email, the link alone signs the user in.
    assert google_login(client, sub=sub)["id"] == user["id"]
    assert client.get("/auth/me", headers=login(client, user["email"])).json()["id"] == user["id"]


@pytest.mark.usefixtures("google")
def test_link_google_rejects_invalid_requests(client: TestClient):
    user, other = create_user(client), create_user(client)
    headers = login(client, user["email"])
    sub = uuid4().hex
    credential = google_token(sub=sub)

    assert client.post("/auth/google/link", json={"credential": credential}).status_code == 401
    assert client.post("/auth/google/link", json={"credential": "not-a-jwt"}, headers=headers).status_code == 400
    assert client.post("/auth/google/link", json={"credential": credential}, headers=headers).status_code == 200
    response = client.post("/auth/google/link", json={"credential": credential}, headers=login(client, other["email"]))
    assert response.status_code == 409
    assert google_login(client, sub=sub)["id"] == user["id"]
