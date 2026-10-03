from io import BytesIO
from unittest.mock import Mock
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import municipalities
from app.common import Location
from conftest import JPEG, create_report, random_location, reference_id


@pytest.mark.parametrize(
    "data, expected",
    [
        (
            "0\n126101_1|Kraków (miasto)|powiat Kraków\n",
            municipalities.Municipality("1261011", "Kraków (miasto)", "powiat Kraków"),
        ),
        (
            "0\n020101_1|Bolesławiec|powiat bolesławiecki\n",
            municipalities.Municipality("0201011", "Bolesławiec", "powiat bolesławiecki"),
        ),
        (
            "0\n120601_2|Czernichów|powiat krakowski\n",
            municipalities.Municipality("1206012", "Czernichów", "powiat krakowski"),
        ),
        (
            "0\n120611_3|Skawina|powiat krakowski\n",
            municipalities.Municipality("1206113", "Skawina", "powiat krakowski"),
        ),
        ("-1 brak wyników\n", None),
    ],
)
def test_resolve_municipality_uses_wgs84_and_normalizes_teryt(monkeypatch, data, expected):
    request = Mock(return_value=BytesIO(data.encode()))
    monkeypatch.setattr(municipalities, "urlopen", request)

    assert municipalities.resolve_municipality(Location(longitude=19.938, latitude=50.061)) == expected

    url = urlparse(request.call_args.args[0].full_url)
    assert url.scheme == "https" and url.hostname == "uldk.gugik.gov.pl"
    assert parse_qs(url.query) == {
        "request": ["GetCommuneByXY"],
        "xy": ["19.938,50.061,4326"],
        "result": ["teryt,commune,county"],
    }
    assert request.call_args.kwargs["timeout"] == 5


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"<html>unavailable</html>",
        b"-1 service error",
        b"0\ninvalid|City|County",
        b"0\n126101_1| |County",
        b"0\n126101_1|City|County|extra",
        b"0\n126101_1|City| ",
        b"0\n126101_1|City|County\n120601_2|Other|County",
        b"0\n126101_9|District|County",
        b"\xff",
        b"x" * (municipalities.MAX_RESPONSE_BYTES + 1),
    ],
)
def test_invalid_or_ambiguous_response_is_unavailable(monkeypatch, data):
    monkeypatch.setattr(municipalities, "urlopen", Mock(return_value=BytesIO(data)))
    with pytest.raises(municipalities.MunicipalityUnavailableError):
        municipalities.resolve_municipality(Location(longitude=19.938, latitude=50.061))


@pytest.mark.parametrize("error", [TimeoutError(), URLError("unavailable")])
def test_network_failure_is_unavailable(monkeypatch, error):
    monkeypatch.setattr(municipalities, "urlopen", Mock(side_effect=error))
    with pytest.raises(municipalities.MunicipalityUnavailableError):
        municipalities.resolve_municipality(Location(longitude=19.938, latitude=50.061))


def test_report_persists_municipality(client: TestClient, signed_in, connection: psycopg.Connection, monkeypatch):
    user, headers = signed_in("user")
    location = random_location()
    resolve = Mock(return_value=municipalities.Municipality("1261011", "Kraków (miasto)", "powiat Kraków"))
    monkeypatch.setattr(municipalities, "resolve_municipality", resolve)

    report = create_report(client, headers, location, photos=[JPEG])

    resolve.assert_called_once_with(Location(**location))
    assert report["municipality_teryt"] == "1261011"
    assert report["municipality_name"] == "Kraków (miasto)"
    assert report["county_teryt"] == "1261"
    assert report["county_name"] == "powiat Kraków"
    assert report["location"] == pytest.approx(location)
    stored = connection.execute(
        "SELECT municipality_teryt, municipality_name, county_teryt, county_name FROM reports WHERE id = %s",
        (report["id"],),
    ).fetchone()
    assert stored == {
        key: report[key] for key in ("municipality_teryt", "municipality_name", "county_teryt", "county_name")
    }
    assert client.get(f"/reports/{report['id']}").json() == report
    assert client.get("/reports", params={"user_id": user["id"]}).json()["items"] == [report]


def test_location_edit_refreshes_municipality_but_text_edit_does_not(client, signed_in, monkeypatch):
    _, headers = signed_in("user")
    report = create_report(client, headers, random_location())
    url = f"/reports/{report['id']}"
    resolve = Mock(return_value=municipalities.Municipality("1206113", "Skawina", "powiat krakowski"))
    monkeypatch.setattr(municipalities, "resolve_municipality", resolve)

    unchanged = client.patch(url, headers=headers, json={"title": "Nowy opis"})
    assert unchanged.status_code == 200
    assert unchanged.json()["municipality_teryt"] == report["municipality_teryt"]
    resolve.assert_not_called()

    location = random_location()
    updated = client.patch(url, headers=headers, json={"location": location})
    assert updated.status_code == 200
    assert updated.json()["municipality_teryt"] == "1206113"
    assert updated.json()["municipality_name"] == "Skawina"
    assert updated.json()["county_teryt"] == "1206"
    assert updated.json()["county_name"] == "powiat krakowski"
    assert updated.json()["master_report_id"] == report["master_report_id"]
    resolve.assert_called_once_with(Location(**location))
    assert client.patch(url, headers=headers, json={"municipality_teryt": "1261011"}).status_code == 422


@pytest.mark.parametrize(
    "outcome, expected_status", [("outside_poland", 422), ("outside_malopolska", 422), ("unavailable", 503)]
)
def test_failed_lookup_does_not_save_or_change_report(
    client, signed_in, connection, upload_dir, monkeypatch, outcome, expected_status
):
    user, headers = signed_in("user")
    report = create_report(client, headers, random_location())
    resolve = Mock(return_value=None)
    if outcome == "unavailable":
        resolve.side_effect = municipalities.MunicipalityUnavailableError
    elif outcome == "outside_malopolska":
        resolve.return_value = municipalities.Municipality("3064011", "Poznań (miasto)", "powiat Poznań")
    monkeypatch.setattr(municipalities, "resolve_municipality", resolve)
    counts = connection.execute(
        "SELECT (SELECT count(*) FROM reports) AS reports, count(*) AS masters FROM master_reports"
    ).fetchone()
    form = {
        "report_category_id": reference_id(client, "/report-categories", "issue"),
        "title": "Dziura",
        "description": "Opis",
        **random_location(),
    }

    response = client.post("/reports", data=form, files=[("photos", ("photo.jpg", JPEG))], headers=headers)
    assert response.status_code == expected_status
    assert (
        connection.execute(
            "SELECT (SELECT count(*) FROM reports) AS reports, count(*) AS masters FROM master_reports"
        ).fetchone()
        == counts
    )
    assert not any(upload_dir.iterdir())
    assert client.get("/reports", params={"user_id": user["id"]}).json()["total"] == 1

    url = f"/reports/{report['id']}"
    response = client.patch(url, headers=headers, json={"location": random_location(), "title": "Changed"})
    assert response.status_code == expected_status
    assert client.get(url).json() == report


def test_unauthorized_location_edit_does_not_call_geocoder(client, signed_in, monkeypatch):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    report = create_report(client, headers, random_location())
    resolve = Mock()
    monkeypatch.setattr(municipalities, "resolve_municipality", resolve)
    response = client.patch(f"/reports/{report['id']}", headers=other_headers, json={"location": random_location()})
    assert response.status_code == 403
    resolve.assert_not_called()
