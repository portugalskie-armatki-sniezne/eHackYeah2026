from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.matching import normalize_title, title_similarity
from conftest import JPEG, PNG, create_report, moved, random_location, reference_id


def test_normalize_title_ignores_case_accents_and_punctuation():
    assert normalize_title("  Dziura, przy ul. DŁUGIEJ! ") == "dziura przy ul dlugiej"
    assert title_similarity("Dziura w jezdni", "dziura w jezdni") == 1


def test_first_report_creates_master(client: TestClient, signed_in):
    user, headers = signed_in("user")
    location = random_location()

    report = create_report(client, headers, location, title="  Dziura w jezdni  ")
    master = client.get(f"/master-reports/{report['master_report_id']}").json()

    assert report["user_id"] == user["id"]
    assert report["title"] == "Dziura w jezdni"
    assert report["location"] == pytest.approx(location)
    assert master["status_id"] == reference_id(client, "/master-report-statuses", "created")
    assert master["responsible_office_id"] is None and master["responsible_service_entity_id"] is None
    assert master["response"] is None
    assert master["report_count"] == 1
    assert {key: master[key] for key in ("report_category_id", "title", "description")} == {
        key: report[key] for key in ("report_category_id", "title", "description")
    }
    assert master["location"] == pytest.approx(location)


def test_similar_report_nearby_joins_master(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location, title="Dziura w jezdni")

    second = create_report(
        client, other_headers, moved(location, north_m=30, east_m=20), title="Dziura w jezdni na Długiej"
    )

    assert second["master_report_id"] == first["master_report_id"]
    assert client.get(f"/master-reports/{first['master_report_id']}").json()["report_count"] == 2


@pytest.mark.parametrize(
    "overrides, offset_m",
    [
        ({"title": "Zepsuta latarnia"}, 5),
        ({"title": "Dziura w jezdni"}, 60),
        ({"title": "Dziura w jezdni", "category": "improvement"}, 5),
    ],
)
def test_report_creates_new_master_for_other_issue_place_or_category(
    client: TestClient, signed_in, overrides: dict[str, str], offset_m: float
):
    _, headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location, title="Dziura w jezdni")

    second = create_report(client, headers, moved(location, north_m=offset_m), **overrides)

    assert second["master_report_id"] != first["master_report_id"]


def test_radius_is_measured_from_master(client: TestClient, signed_in):
    _, headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location)
    second = create_report(client, headers, moved(location, north_m=40))

    # 80 m from the master, even though only 40 m from the second report.
    third = create_report(client, headers, moved(location, north_m=80))

    assert second["master_report_id"] == first["master_report_id"]
    assert third["master_report_id"] != first["master_report_id"]


def test_finished_master_is_not_matched(client: TestClient, signed_in, connection: psycopg.Connection):
    _, headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location)
    connection.execute(
        "UPDATE master_reports SET status_id = (SELECT id FROM master_report_statuses WHERE name = 'finished') "
        "WHERE id = %s",
        (first["master_report_id"],),
    )

    second = create_report(client, headers, location)

    assert second["master_report_id"] != first["master_report_id"]


def test_most_similar_master_wins_and_distance_breaks_ties(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, office_headers = signed_in("office")
    location = random_location()

    def master_at(title: str, north_m: float) -> str:
        # created elsewhere and moved, so it does not join the other masters.
        master_id = create_report(client, headers, random_location(), title=title)["master_report_id"]
        response = client.patch(
            f"/master-reports/{master_id}", headers=office_headers, json={"location": moved(location, north_m=north_m)}
        )
        assert response.status_code == 200
        return master_id

    exact_far = master_at("Dziura w jezdni", 40)
    similar_near = master_at("Dziura w chodniku", 2)

    assert create_report(client, headers, location, title="Dziura w jezdni")["master_report_id"] == exact_far
    exact_near = master_at("Dziura w jezdni", -20)
    assert create_report(client, headers, location, title="Dziura w jezdni")["master_report_id"] == exact_near
    assert create_report(client, headers, location, title="Dziura w chodniku")["master_report_id"] == similar_near


def test_report_matches_titles_of_attached_reports(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, office_headers = signed_in("office")
    location = random_location()
    first = create_report(client, headers, location, title="Dziura w jezdni")
    synonym = create_report(client, headers, location, title="Wyrwa w asfalcie")
    assert synonym["master_report_id"] != first["master_report_id"]
    response = client.post(
        f"/reports/{synonym['id']}/move", headers=office_headers, json={"master_report_id": first["master_report_id"]}
    )
    assert response.status_code == 200

    report = create_report(client, headers, location, title="Wyrwa w asfalcie przy przejściu")

    assert report["master_report_id"] == first["master_report_id"]


def test_create_report_with_photos(client: TestClient, signed_in, upload_dir):
    _, headers = signed_in("user")

    report = create_report(client, headers, random_location(), photos=[JPEG, PNG])

    assert len(report["photos"]) == 2
    for photo in report["photos"]:
        assert photo["report_id"] == report["id"]
        assert photo["storage_key"].startswith(f"reports/{report['id']}/")
        assert (upload_dir / photo["storage_key"]).is_file()
        # files are public, so the app can show them without a token.
        response = client.get(photo["url"])
        assert response.status_code == 200
        assert response.content in (JPEG, PNG)
        assert response.headers["content-type"] == ("image/jpeg" if response.content == JPEG else "image/png")
    assert client.get(f"/photos/{uuid4()}/file").status_code == 404


def test_create_report_rejects_invalid_photos(client: TestClient, signed_in, upload_dir):
    _, headers = signed_in("user")
    form = {
        "report_category_id": reference_id(client, "/report-categories", "issue"),
        "title": "Dziura",
        "description": "Dziura w jezdni",
        **random_location(),
    }

    def post(photos: list[bytes]) -> int:
        files = [("photos", (f"photo-{index}.jpg", data)) for index, data in enumerate(photos)]
        return client.post("/reports", data=form, files=files, headers=headers).status_code

    assert post([b"GIF89a not supported"]) == 422
    assert post([JPEG] * 6) == 422
    assert post([JPEG, JPEG + b"\0" * (10 * 1024 * 1024)]) == 413
    assert not any(upload_dir.iterdir())


def test_create_report_validates_input(client: TestClient, signed_in):
    _, headers = signed_in("user")
    form = {
        "report_category_id": reference_id(client, "/report-categories", "issue"),
        "title": "Dziura",
        "description": "Dziura w jezdni",
        **random_location(),
    }

    assert client.post("/reports", data=form).status_code == 401
    response = client.post("/reports", data=form | {"report_category_id": 0}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Report category not found"
    for invalid in ({"title": "   "}, {"description": ""}, {"longitude": 181}, {"latitude": -91}):
        assert client.post("/reports", data=form | invalid, headers=headers).status_code == 422


def test_list_and_get_reports_require_login(client: TestClient, signed_in):
    user, headers = signed_in("user")
    _, other_headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location)
    second = create_report(client, headers, moved(location, north_m=10))
    other = create_report(client, other_headers, moved(location, north_m=1000))

    def ids(**params: object) -> set[str]:
        page = client.get("/reports", params=params | {"limit": 200}, headers=headers).json()
        return {report["id"] for report in page["items"]}

    assert client.get("/reports").status_code == 401
    assert client.get(f"/reports/{first['id']}").status_code == 401
    assert client.get(f"/reports/{other['id']}", headers=headers).json() == other
    assert client.get(f"/reports/{uuid4()}", headers=headers).status_code == 404
    assert ids(user_id=user["id"]) == {first["id"], second["id"]}
    assert ids(master_report_id=first["master_report_id"]) == {first["id"], second["id"]}
    assert ids(**location, radius_m=100) == {first["id"], second["id"]}
    assert client.get("/reports", params=location, headers=headers).status_code == 422


def test_update_report(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    _, office_headers = signed_in("office")
    _, admin_headers = signed_in("admin")
    report = create_report(client, headers, random_location())
    url = f"/reports/{report['id']}"
    new_location = random_location()

    response = client.patch(url, json={"title": "Głęboka dziura", "location": new_location}, headers=headers)

    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Głęboka dziura"
    assert updated["location"] == pytest.approx(new_location)
    # edits do not move the report to another master.
    assert updated["master_report_id"] == report["master_report_id"]
    assert client.patch(url, json={"title": "X"}, headers=other_headers).status_code == 403
    assert client.patch(url, json={"title": "X"}, headers=office_headers).status_code == 403
    assert client.patch(url, json={"title": "Admin"}, headers=admin_headers).json()["title"] == "Admin"
    assert client.patch(url, json={"title": None}, headers=headers).status_code == 422
    assert client.patch(url, json={"master_report_id": None}, headers=headers).status_code == 422
    assert client.patch(url, json={"report_category_id": 0}, headers=headers).status_code == 404
    assert client.patch(f"/reports/{uuid4()}", json={"title": "X"}, headers=headers).status_code == 404


def test_delete_report_removes_photos_and_empty_master(client: TestClient, signed_in, upload_dir):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location, photos=[JPEG])
    second = create_report(client, other_headers, location)
    master_url = f"/master-reports/{first['master_report_id']}"

    assert client.delete(f"/reports/{first['id']}", headers=other_headers).status_code == 403
    assert client.delete(f"/reports/{first['id']}", headers=headers).status_code == 204

    assert not (upload_dir / first["photos"][0]["storage_key"]).exists()
    assert client.get(master_url).json()["report_count"] == 1
    assert client.delete(f"/reports/{second['id']}", headers=other_headers).status_code == 204
    assert client.get(master_url).status_code == 404
    assert client.delete(f"/reports/{second['id']}", headers=other_headers).status_code == 404


def test_move_report(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, office_headers = signed_in("office")
    location = random_location()
    first = create_report(client, headers, location)
    second = create_report(client, headers, location)
    other = create_report(client, headers, random_location(), title="Zepsuta latarnia")
    url = f"/reports/{second['id']}/move"

    assert client.post(url, json={"master_report_id": None}, headers=headers).status_code == 403
    split = client.post(url, json={"master_report_id": None}, headers=office_headers).json()
    assert split["master_report_id"] not in (None, first["master_report_id"])
    assert client.get(f"/master-reports/{split['master_report_id']}").json()["title"] == second["title"]

    moved_report = client.post(url, json={"master_report_id": other["master_report_id"]}, headers=office_headers).json()
    assert moved_report["master_report_id"] == other["master_report_id"]
    # the master created by the split has no reports left.
    assert client.get(f"/master-reports/{split['master_report_id']}").status_code == 404
    assert client.post(url, json={"master_report_id": str(uuid4())}, headers=office_headers).status_code == 404
    assert client.post(url, json={}, headers=office_headers).status_code == 422


def test_report_photos(client: TestClient, signed_in, upload_dir):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    report = create_report(client, headers, random_location(), photos=[JPEG] * 4)
    url = f"/reports/{report['id']}/photos"

    assert client.post(url, files=[("photos", ("a.png", PNG))], headers=other_headers).status_code == 403
    assert client.post(url, files=[("photos", ("a.png", PNG))] * 2, headers=headers).status_code == 422
    added = client.post(url, files=[("photos", ("a.png", PNG))], headers=headers)
    assert added.status_code == 201
    photo = added.json()[0]
    assert len(client.get(url, headers=headers).json()) == 5
    assert client.get(url).status_code == 401

    assert client.delete(f"{url}/{photo['id']}", headers=other_headers).status_code == 403
    assert client.delete(f"{url}/{photo['id']}", headers=headers).status_code == 204
    assert not (upload_dir / photo["storage_key"]).exists()
    assert client.delete(f"{url}/{photo['id']}", headers=headers).status_code == 404
    assert client.get(f"/reports/{uuid4()}/photos", headers=headers).status_code == 404
