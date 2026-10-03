from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient


def test_reference_data_is_public(client: TestClient):
    categories = client.get("/report-categories").json()
    statuses = client.get("/master-report-statuses").json()

    assert {"improvement", "issue"} <= {category["name"] for category in categories}
    assert {"created", "reported", "inprogress", "finished"} <= {status["name"] for status in statuses}
    assert all(isinstance(item["id"], int) for item in categories + statuses)


def test_institution_contacts(client: TestClient, connection: psycopg.Connection):
    name = f"Gmina 100%_{uuid4().hex}"
    teryt_code = f"{uuid4().int % 10**7:07d}"
    institution_id = connection.execute(
        "INSERT INTO institution_contacts (teryt_code, local_government_name, province, local_government_type) "
        "VALUES (%s, %s, 'małopolskie', 'GM') RETURNING id",
        (teryt_code, name),
    ).fetchone()["id"]

    institution = client.get(f"/institution-contacts/{institution_id}").json()

    assert institution["teryt_code"] == teryt_code
    assert institution["local_government_name"] == name
    assert institution["email"] is None
    assert client.get("/institution-contacts", params={"teryt_code": teryt_code}).json()["items"] == [institution]
    # % and _ in q are matched literally.
    assert client.get("/institution-contacts", params={"q": name[6:].upper()}).json()["items"] == [institution]
    assert client.get("/institution-contacts", params={"q": "100__"}).json()["total"] == 0
    page = client.get("/institution-contacts",
                      params={"province": "małopolskie", "local_government_type": "GM", "limit": 200}).json()
    assert institution in page["items"]
    assert client.get("/institution-contacts/0").status_code == 404
