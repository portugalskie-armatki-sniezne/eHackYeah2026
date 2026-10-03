import math
import random
from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from psycopg.rows import dict_row


def pytest_configure() -> None:
    # load configuration before application imports create the connection pool.
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-bytes")


@pytest.fixture(autouse=True)
def upload_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def connection() -> Iterator[psycopg.Connection]:
    from app.db import conninfo

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
    from app.db import get_connection
    from app.main import app

    app.dependency_overrides[get_connection] = lambda: connection
    # no context manager, so the lifespan does not open the shared pool.
    yield TestClient(app)
    app.dependency_overrides.clear()


def user_payload(**overrides: object) -> dict[str, object]:
    return {
        "first_name": "Anna",
        "last_name": "Nowak",
        "email": f"anna-{uuid4().hex}@example.com",
        "phone": f"+48{uuid4().int % 10**9:09d}",
        "password": "tajne-haslo",
    } | overrides


def create_user(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post("/users", json=user_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, username: str, password: str = "tajne-haslo") -> dict[str, str]:
    response = client.post("/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def signed_in(
    client: TestClient, connection: psycopg.Connection
) -> Callable[[str], tuple[dict[str, object], dict[str, str]]]:
    """create a user with the given role and return it with authorization headers."""

    def sign_in(role: str = "user") -> tuple[dict[str, object], dict[str, str]]:
        user = create_user(client)
        connection.execute("UPDATE users SET role = %s WHERE id = %s", (role, user["id"]))
        headers = login(client, user["email"])
        return client.get("/auth/me", headers=headers).json(), headers

    return sign_in


JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16


def random_location() -> dict[str, float]:
    # a random point in Poland, so tests do not match masters from other data.
    return {"longitude": random.uniform(14.5, 23.5), "latitude": random.uniform(49.5, 54.5)}


def moved(location: dict[str, float], north_m: float = 0, east_m: float = 0) -> dict[str, float]:
    meters_per_degree = 111_320
    return {
        "longitude": location["longitude"]
        + east_m / (meters_per_degree * math.cos(math.radians(location["latitude"]))),
        "latitude": location["latitude"] + north_m / meters_per_degree,
    }


def reference_id(client: TestClient, path: str, name: str) -> int:
    return next(item["id"] for item in client.get(path).json() if item["name"] == name)


def create_report(
    client: TestClient,
    headers: dict[str, str],
    location: dict[str, float],
    photos: list[bytes] | None = None,
    category: str = "issue",
    **overrides: object,
) -> dict[str, object]:
    form = {
        "report_category_id": reference_id(client, "/report-categories", category),
        "title": "Dziura w jezdni",
        "description": "Głęboka dziura na pasie ruchu.",
        **location,
    } | overrides
    files = [("photos", (f"photo-{index}", data)) for index, data in enumerate(photos or [])]
    response = client.post("/reports", data=form, files=files or None, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
