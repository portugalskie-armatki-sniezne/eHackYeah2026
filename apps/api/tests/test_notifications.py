from uuid import uuid4

from fastapi.testclient import TestClient

from conftest import create_report, random_location, reference_id


def status_id(client: TestClient, name: str) -> int:
    return reference_id(client, "/master-report-statuses", name)


def test_status_changes_and_comments_reach_the_reporter(client: TestClient, signed_in):
    reporter, headers = signed_in("user")
    _, office_headers = signed_in("office")
    master_id = create_report(client, headers, random_location())["master_report_id"]

    assert client.get("/notifications").status_code == 401
    assert client.get("/notifications", headers=headers).json()["total"] == 0

    patch = f"/master-reports/{master_id}"
    client.patch(patch, json={"status_id": status_id(client, "inprogress")}, headers=office_headers)
    client.patch(patch, json={"response": "Zlecone do naprawy."}, headers=office_headers)
    client.patch(patch, json={"status_id": status_id(client, "finished")}, headers=office_headers)
    client.post(f"/master-reports/{master_id}/comments", json={"content": "Naprawione"}, headers=office_headers)
    # the reporter's own comment is not news to them.
    client.post(f"/master-reports/{master_id}/comments", json={"content": "Dziekuje"}, headers=headers)

    page = client.get("/notifications", headers=headers).json()
    # created_at is the same within the test transaction, so the feed's order is not asserted.
    assert sorted(item["kind"] for item in page["items"]) == [
        "comment",
        "status_finished",
        "status_inprogress",
        "update",
    ]
    assert all(item["user_id"] == reporter["id"] for item in page["items"])
    assert all(item["master_report_id"] == master_id for item in page["items"])
    assert all(item["subject"] == "Dziura w jezdni" for item in page["items"])
    update = next(item for item in page["items"] if item["kind"] == "update")
    assert update["detail"] == "Zlecone do naprawy."
    assert client.get("/notifications/unread-count", headers=headers).json() == {"count": 4}

    # setting the same status again is not a change, so it tells nobody.
    client.patch(patch, json={"status_id": status_id(client, "finished")}, headers=office_headers)
    assert client.get("/notifications/unread-count", headers=headers).json() == {"count": 4}


def test_reading_and_dismissing_notifications(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    master_id = create_report(client, headers, random_location())["master_report_id"]
    client.post(f"/master-reports/{master_id}/comments", json={"content": "Tez tam bylem"}, headers=other_headers)
    notification = client.get("/notifications", headers=headers).json()["items"][0]

    # another account cannot see, read, or dismiss it.
    assert client.get("/notifications", headers=other_headers).json()["total"] == 0
    assert client.put(f"/notifications/{notification['id']}/read", headers=other_headers).status_code == 404
    assert client.delete(f"/notifications/{notification['id']}", headers=other_headers).status_code == 404

    read = client.put(f"/notifications/{notification['id']}/read", headers=headers).json()
    assert read["read_at"] is not None
    # reading twice keeps the first timestamp.
    assert client.put(f"/notifications/{notification['id']}/read", headers=headers).json() == read
    assert client.get("/notifications", params={"unread": True}, headers=headers).json()["total"] == 0
    assert client.post("/notifications/read-all", headers=headers).json() == {"count": 0}

    assert client.delete(f"/notifications/{notification['id']}", headers=headers).status_code == 204
    assert client.delete(f"/notifications/{notification['id']}", headers=headers).status_code == 404
    assert client.get("/notifications", headers=headers).json()["total"] == 0
    assert client.put(f"/notifications/{uuid4()}/read", headers=headers).status_code == 404
