from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import JPEG, PNG, create_report, moved, random_location, reference_id


def create_institution(connection: psycopg.Connection, **values: str) -> int:
    values = {"teryt_code": f"{uuid4().int % 10**7:07d}", "local_government_name": "Gmina Testowa"} | values
    return connection.execute(
        "INSERT INTO institution_contacts (teryt_code, local_government_name, province, county) "
        "VALUES (%(teryt_code)s, %(local_government_name)s, %(province)s, %(county)s) RETURNING id",
        {"province": None, "county": None} | values,
    ).fetchone()["id"]


def test_master_reports_are_public(client: TestClient, signed_in):
    _, headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location, photos=[JPEG])
    second = create_report(client, headers, location, photos=[PNG])
    master_id = first["master_report_id"]

    master = client.get(f"/master-reports/{master_id}").json()

    assert master["report_count"] == 2
    assert {photo["id"] for photo in master["photos"]} == {
        photo["id"] for photo in first["photos"] + second["photos"]}
    assert client.get(f"/master-reports/{uuid4()}").status_code == 404


def test_list_master_reports_with_filters(client: TestClient, signed_in, connection: psycopg.Connection):
    _, headers = signed_in("user")
    _, office_headers = signed_in("office")
    location = random_location()
    issue = create_report(client, headers, location)["master_report_id"]
    improvement = create_report(client, headers, moved(location, north_m=10), category="improvement",
                                title="Nowa ławka")["master_report_id"]
    institution_id = create_institution(connection)
    finished = reference_id(client, "/master-report-statuses", "finished")
    client.patch(f"/master-reports/{improvement}", headers=office_headers,
                 json={"status_id": finished, "responsible_institution_id": institution_id})

    def ids(**params: object) -> set[str]:
        page = client.get("/master-reports", params=params | {"limit": 200}).json()
        return {master["id"] for master in page["items"]}

    assert ids(**location, radius_m=100) == {issue, improvement}
    assert ids(**location, radius_m=100, status_id=finished) == {improvement}
    assert ids(**location, radius_m=100,
               report_category_id=reference_id(client, "/report-categories", "issue")) == {issue}
    assert ids(responsible_institution_id=institution_id) == {improvement}
    page = client.get("/master-reports", params={"limit": 1}).json()
    assert page["limit"] == 1 and page["total"] >= 2 and len(page["items"]) == 1
    assert "photos" not in page["items"][0]
    assert client.get("/master-reports", params={"radius_m": 10}).status_code == 422


@pytest.mark.parametrize("role", ["office", "admin"])
def test_staff_updates_master_report(client: TestClient, signed_in, connection: psycopg.Connection, role: str):
    _, headers = signed_in("user")
    _, staff_headers = signed_in(role)
    report = create_report(client, headers, random_location())
    url = f"/master-reports/{report['master_report_id']}"
    institution_id = create_institution(connection)
    finished = reference_id(client, "/master-report-statuses", "finished")
    created = reference_id(client, "/master-report-statuses", "created")

    response = client.patch(url, headers=staff_headers, json={
        "status_id": finished, "responsible_institution_id": institution_id,
        "response": "  Naprawione.  ", "title": "Dziura przy Długiej"})

    assert response.status_code == 200
    master = response.json()
    assert master["status_id"] == finished
    assert master["responsible_institution_id"] == institution_id
    assert master["response"] == "Naprawione."
    assert master["title"] == "Dziura przy Długiej"
    # the report keeps its own content.
    assert client.get(f"/reports/{report['id']}", headers=headers).json()["title"] == report["title"]
    # any status change is allowed, also back to created.
    cleared = client.patch(url, headers=staff_headers,
                           json={"status_id": created, "response": None, "responsible_institution_id": None})
    assert cleared.json()["status_id"] == created
    assert cleared.json()["response"] is None and cleared.json()["responsible_institution_id"] is None


def test_update_master_report_rejects_invalid_changes(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, office_headers = signed_in("office")
    url = f"/master-reports/{create_report(client, headers, random_location())['master_report_id']}"

    assert client.patch(url, json={"title": "X"}).status_code == 401
    assert client.patch(url, json={"title": "X"}, headers=headers).status_code == 403
    for invalid in ({"title": None}, {"status_id": None}, {"location": {"longitude": 200, "latitude": 0}},
                    {"unknown": 1}):
        assert client.patch(url, json=invalid, headers=office_headers).status_code == 422
    for missing, detail in (({"status_id": 0}, "Status not found"),
                            ({"report_category_id": 0}, "Report category not found"),
                            ({"responsible_institution_id": 0}, "Institution not found")):
        response = client.patch(url, json=missing, headers=office_headers)
        assert response.status_code == 404 and response.json()["detail"] == detail
    assert client.patch(f"/master-reports/{uuid4()}", json={"title": "X"},
                        headers=office_headers).status_code == 404


def test_only_admin_deletes_master_report_without_reports(client: TestClient, signed_in,
                                                          connection: psycopg.Connection):
    _, headers = signed_in("user")
    _, office_headers = signed_in("office")
    _, admin_headers = signed_in("admin")
    report = create_report(client, headers, random_location())
    url = f"/master-reports/{report['master_report_id']}"

    assert client.delete(url, headers=office_headers).status_code == 403
    assert client.delete(url, headers=admin_headers).status_code == 409
    connection.execute("UPDATE reports SET master_report_id = NULL WHERE id = %s", (report["id"],))
    assert client.delete(url, headers=admin_headers).status_code == 204
    assert client.delete(url, headers=admin_headers).status_code == 404
