from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from conftest import JPEG, PNG, create_report, moved, random_location, reference_id


def add_photo(client: TestClient, master_id: str, headers: dict[str, str], image: bytes = PNG):
    return client.post(
        f"/master-reports/{master_id}/photos",
        files={"photo": ("evidence.png", image)},
        headers=headers,
    )


@pytest.mark.parametrize("category", ["issue", "improvement"])
def test_photo_creates_an_owned_copy_in_the_same_case(client, signed_in, connection, category):
    author, headers = signed_in()
    uploader, other_headers = signed_in()
    source = create_report(client, headers, random_location(), category=category)
    master_id = source["master_report_id"]
    master_before = client.get(f"/master-reports/{master_id}").json()
    delivery_count = connection.execute("SELECT count(*) AS n FROM mail_delivery_jobs").fetchone()["n"]

    response = add_photo(client, master_id, other_headers)

    assert response.status_code == 201, response.text
    report = response.json()
    assert report["id"] != source["id"]
    assert report["user_id"] == uploader["id"] != author["id"]
    for field in (
        "master_report_id",
        "report_category_id",
        "title",
        "description",
        "location",
        "municipality_teryt",
        "municipality_name",
        "county_teryt",
        "county_name",
    ):
        assert report[field] == source[field]
    assert client.get(f"/reports/{source['id']}").json() == source
    assert len(report["photos"]) == 1
    photo = report["photos"][0]
    file = client.get(photo["url"])
    assert file.status_code == 200 and file.content == PNG
    assert file.headers["content-type"] == "image/png"
    master = client.get(f"/master-reports/{master_id}").json()
    assert master["report_count"] == master_before["report_count"] + 1
    assert master["photo_url"] == photo["url"]
    assert master["photos"] == report["photos"]
    assert master["pending_photo_id"] is None
    assert client.get(f"/master-reports/{master_id}/photo-proposals").json()["total"] == 0
    assert client.get("/notifications", headers=headers).json()["total"] == 0
    assert client.get("/notifications", headers=other_headers).json()["total"] == 0
    assert connection.execute("SELECT count(*) AS n FROM mail_delivery_jobs").fetchone()["n"] == delivery_count
    own = client.get("/reports", params={"user_id": uploader["id"]}).json()["items"]
    assert report in own


def test_existing_photos_and_finished_status_are_preserved(client, signed_in):
    _, headers = signed_in()
    _, office_headers = signed_in("office")
    source = create_report(client, headers, random_location(), photos=[JPEG])
    master_id = source["master_report_id"]
    finished = reference_id(client, "/master-report-statuses", "finished")
    response = client.patch(
        f"/master-reports/{master_id}",
        headers=office_headers,
        json={"status_id": finished, "title": "Zaktualizowana sprawa", "description": "Opis sprawy po aktualizacji"},
    )
    assert response.status_code == 200
    master_before = client.get(f"/master-reports/{master_id}").json()

    response = add_photo(client, master_id, headers)

    assert response.status_code == 201, response.text
    report = response.json()
    assert report["title"] == source["title"]
    assert report["description"] == source["description"]
    assert len(report["photos"]) == 1
    assert report["photos"][0]["id"] != source["photos"][0]["id"]
    master = client.get(f"/master-reports/{master_id}").json()
    for field in ("status_id", "title", "description", "responsible_office_id", "responsible_service_entity_id"):
        assert master[field] == master_before[field]
    assert {photo["id"] for photo in master["photos"]} == {source["photos"][0]["id"], report["photos"][0]["id"]}


def test_oldest_report_is_copied_and_the_original_author_keeps_the_case(client, signed_in, connection):
    author, headers = signed_in()
    _, other_headers = signed_in()
    location = random_location()
    source = create_report(client, headers, location)
    master_id = source["master_report_id"]
    connection.execute("UPDATE reports SET created_at = '2000-01-01' WHERE id = %s", (source["id"],))
    second = create_report(client, other_headers, moved(location, north_m=10))
    assert second["master_report_id"] == master_id
    connection.execute(
        "UPDATE reports SET title = 'Inny opis miejsca', description = 'Nowsze zgłoszenie' WHERE id = %s",
        (second["id"],),
    )

    response = add_photo(client, master_id, other_headers)

    assert response.status_code == 201, response.text
    report = response.json()
    assert report["title"] == source["title"]
    assert report["description"] == source["description"]
    assert report["location"] == source["location"]
    assert client.get(f"/master-reports/{master_id}").json()["author_id"] == author["id"]


def test_uploader_can_remove_only_their_copy_and_receives_case_updates(client, signed_in, upload_dir):
    _, headers = signed_in()
    _, other_headers = signed_in()
    _, office_headers = signed_in("office")
    source = create_report(client, headers, random_location())
    master_id = source["master_report_id"]
    report = add_photo(client, master_id, other_headers).json()
    status_id = reference_id(client, "/master-report-statuses", "inprogress")
    response = client.patch(f"/master-reports/{master_id}", headers=office_headers, json={"status_id": status_id})
    assert response.status_code == 200
    notices = client.get("/notifications", headers=other_headers).json()["items"]
    assert len(notices) == 1 and notices[0]["kind"] == "status_inprogress"
    assert client.delete(f"/reports/{source['id']}", headers=other_headers).status_code == 403
    assert client.delete(f"/reports/{report['id']}", headers=headers).status_code == 403
    assert client.delete(f"/reports/{report['id']}", headers=other_headers).status_code == 204
    assert not (upload_dir / report["photos"][0]["storage_key"]).exists()
    master = client.get(f"/master-reports/{master_id}").json()
    assert master["report_count"] == 1 and master["photos"] == []
    assert client.get(f"/reports/{source['id']}").status_code == 200


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_existing_proposals_remain_decidable_after_a_direct_upload(client, signed_in, decision):
    _, headers = signed_in()
    _, other_headers = signed_in()
    source = create_report(client, headers, random_location())
    master_id = source["master_report_id"]
    response = client.post(
        f"/master-reports/{master_id}/photo-proposals", headers=other_headers, files={"photo": ("old.jpg", JPEG)}
    )
    assert response.status_code == 201
    proposal = response.json()
    report = add_photo(client, master_id, headers).json()

    response = client.post(f"/photo-proposals/{proposal['id']}/{decision}", headers=headers)

    assert response.status_code == 200, response.text
    master = client.get(f"/master-reports/{master_id}").json()
    assert master["pending_photo_id"] is None
    assert report["photos"][0]["id"] in {photo["id"] for photo in master["photos"]}
    assert client.get(report["photos"][0]["url"]).content == PNG


def test_invalid_uploads_do_not_create_reports(client, signed_in, connection, upload_dir):
    _, headers = signed_in()
    source = create_report(client, headers, random_location())
    master_id = source["master_report_id"]
    assert add_photo(client, master_id, {}).status_code == 401
    assert client.post(f"/master-reports/{master_id}/photos", headers=headers).status_code == 422
    assert add_photo(client, master_id, headers, b"not-an-image").status_code == 422
    assert add_photo(client, master_id, headers, JPEG + b"0" * (10 * 1024 * 1024)).status_code == 413
    assert add_photo(client, str(uuid4()), headers).status_code == 404
    assert client.get(f"/master-reports/{master_id}").json()["report_count"] == 1
    assert not list(upload_dir.rglob("*.*"))
    connection.execute("DELETE FROM reports WHERE id = %s", (source["id"],))
    assert add_photo(client, master_id, headers).status_code == 409


def test_failed_save_removes_the_copy_and_its_file(client, signed_in, monkeypatch, upload_dir):
    from app import master_reports

    _, headers = signed_in()
    source = create_report(client, headers, random_location())
    master_id = source["master_report_id"]
    save_photos = master_reports.save_photos

    def fail_after_save(*args):
        save_photos(*args)
        raise OSError("test storage failure")

    monkeypatch.setattr(master_reports, "save_photos", fail_after_save)
    with pytest.raises(OSError, match="test storage failure"):
        add_photo(client, master_id, headers)

    master = client.get(f"/master-reports/{master_id}").json()
    assert master["report_count"] == 1 and master["photos"] == []
    assert not list(upload_dir.rglob("*.*"))
