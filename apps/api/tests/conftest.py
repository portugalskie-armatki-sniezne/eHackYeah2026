from collections.abc import Callable, Iterator
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.db import conninfo, get_connection
from app.main import app


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-bytes")


@pytest.fixture
def connection() -> Iterator[psycopg.Connection]:
    try:
        connection = psycopg.connect(conninfo(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("database is not available, run `task db` first")
    with connection:
        # keep an open transaction so endpoint transactions become savepoints and nothing is committed.
        connection.execute("SELECT 1")
        yield connection
        connection.rollback()


@pytest.fixture
def client(connection: psycopg.Connection) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: connection
    # no context manager, so the lifespan does not open the shared pool.
    yield TestClient(app)
    app.dependency_overrides.clear()


def user_payload(**overrides: object) -> dict[str, object]:
    return {
        "first_name": "Anna",
        "last_name": "Nowak",
        "email": f"anna-{uuid4().hex}@example.com",
        "phone": "+48123456789",
        "password": "tajne-haslo",
    } | overrides


def create_user(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post("/users", json=user_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str, password: str = "tajne-haslo") -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def signed_in(client: TestClient, connection: psycopg.Connection
              ) -> Callable[[str], tuple[dict[str, object], dict[str, str]]]:
    """create a user with the given role and return it with authorization headers."""

    def sign_in(role: str = "user") -> tuple[dict[str, object], dict[str, str]]:
        user = create_user(client)
        connection.execute("UPDATE users SET role = %s WHERE id = %s", (role, user["id"]))
        return user | {"role": role}, login(client, user["email"])

    return sign_in
