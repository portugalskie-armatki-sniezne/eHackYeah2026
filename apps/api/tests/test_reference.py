from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from app.db import get_connection
from app.main import app


def test_browser_requests_from_other_origins_are_allowed(client: TestClient):
    origin = "https://web.example.com"

    preflight = client.options(
        "/reports",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == "*"
    assert "authorization" in preflight.headers["Access-Control-Allow-Headers"].lower()
    response = client.get("/report-categories", headers={"Origin": origin})
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_busy_database_returns_503(client: TestClient):
    def no_connection():
        raise PoolTimeout("couldn't get a connection after 10.00 sec")

    app.dependency_overrides[get_connection] = no_connection

    response = client.get("/report-categories")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is busy, try again"
    assert response.headers["Retry-After"] == "5"


def test_reference_data_is_public(client: TestClient):
    categories = client.get("/report-categories").json()
    statuses = client.get("/master-report-statuses").json()

    assert {"improvement", "issue"} <= {category["name"] for category in categories}
    assert {"created", "reported", "inprogress", "finished"} <= {status["name"] for status in statuses}
    assert all(isinstance(item["id"], int) for item in categories + statuses)


def test_institution_contacts_read_offices(client: TestClient, connection: psycopg.Connection):
    name = f"Gmina 100%_{uuid4().hex}"
    teryt_code = f"{uuid4().int % 10**7:07d}"
    office_id = connection.execute(
        "INSERT INTO local_government_offices (teryt_code, local_government_name, province, local_government_type) "
        "VALUES (%s, %s, 'małopolskie', 'GM') RETURNING id",
        (teryt_code, name),
    ).fetchone()["id"]

    office = client.get(f"/institution-contacts/{office_id}").json()

    assert office["teryt_code"] == teryt_code
    assert office["local_government_name"] == name
    assert office["email"] is None
    assert client.get("/institution-contacts", params={"teryt_code": teryt_code}).json()["items"] == [office]
    # % and _ in q are matched literally.
    assert client.get("/institution-contacts", params={"q": name[6:].upper()}).json()["items"] == [office]
    assert client.get("/institution-contacts", params={"q": "100__"}).json()["total"] == 0
    page = client.get(
        "/institution-contacts", params={"province": "małopolskie", "local_government_type": "GM", "limit": 200}
    ).json()
    assert office in page["items"]
    assert client.get("/institution-contacts/0").status_code == 404
