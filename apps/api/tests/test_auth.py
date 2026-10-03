from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from conftest import create_user, login


def test_login_returns_token_for_current_user(client: TestClient):
    user = create_user(client)

    response = client.post("/auth/login", data={"username": user["email"], "password": "tajne-haslo"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json() == user


def test_login_with_phone(client: TestClient):
    user = create_user(client, email=None, phone="+48 600-100-200")

    for username in ("+48600100200", "+48 600 100 200"):
        headers = login(client, username)
        assert client.get("/auth/me", headers=headers).json()["id"] == user["id"]


def test_login_rejects_wrong_credentials(client: TestClient):
    user = create_user(client)

    for username, password in ((user["email"], "zle-haslo"), (user["phone"], "zle-haslo"),
                               ("missing@example.com", "tajne-haslo"), ("+48000000000", "tajne-haslo")):
        response = client.post("/auth/login", data={"username": username, "password": password})
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_protected_endpoint_requires_valid_token(client: TestClient):
    user = create_user(client)
    expired = jwt.encode(
        {"sub": user["id"], "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        "test-only-secret-with-at-least-32-bytes", algorithm="HS256",
    )
    forged = jwt.encode(
        {"sub": user["id"], "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "another-secret-with-at-least-32-bytes!!", algorithm="HS256",
    )

    assert client.get("/auth/me").status_code == 401
    for token in ("not-a-jwt", expired, forged):
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_of_deleted_user_is_rejected(client: TestClient):
    user = create_user(client)
    headers = login(client, user["email"])

    assert client.delete(f"/users/{user['id']}", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_token_with_unknown_user_is_rejected(client: TestClient):
    token = jwt.encode(
        {"sub": str(uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "test-only-secret-with-at-least-32-bytes", algorithm="HS256",
    )

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
