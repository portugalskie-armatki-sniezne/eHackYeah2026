from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from threading import Event, Lock
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import municipalities
from app.common import Location
from conftest import JPEG, create_report, random_location, reference_id


@pytest.fixture(autouse=True)
def municipality_resolver(monkeypatch):
    resolver = municipalities.MunicipalityResolver()
    monkeypatch.setattr(municipalities, "_resolver", resolver)
    monkeypatch.setattr(municipalities, "sleep", Mock())
    yield resolver
    resolver._executor.shutdown(wait=True, cancel_futures=True)


def lookup_response(teryt="126101_1"):
    return BytesIO(f"0\n{teryt}|Kraków (miasto)|powiat Kraków\n".encode())


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
    request = Mock(side_effect=error)
    monkeypatch.setattr(municipalities, "urlopen", request)
    with pytest.raises(municipalities.MunicipalityUnavailableError):
        municipalities.resolve_municipality(Location(longitude=19.938, latitude=50.061))
    assert request.call_count == municipalities.MAX_ATTEMPTS


def test_success_is_cached_for_exact_coordinates(monkeypatch):
    request = Mock(side_effect=lambda *args, **kwargs: lookup_response())
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = Location(longitude=19.938, latitude=50.061)

    expected = municipalities.resolve_municipality(location)
    assert municipalities.resolve_municipality(location) == expected
    request.assert_called_once()
    municipalities.resolve_municipality(Location(longitude=19.9380001, latitude=50.061))
    assert request.call_count == 2


@pytest.mark.parametrize("error", [TimeoutError(), URLError("unavailable"), HTTPError("", 503, "", {}, None)])
def test_temporary_failure_retries_and_caches_recovery(monkeypatch, error):
    request = Mock(side_effect=[error, lookup_response()])
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = Location(longitude=19.938, latitude=50.061)

    result = municipalities.resolve_municipality(location)
    assert result.teryt == "1261011"
    assert request.call_count == 2
    assert municipalities.resolve_municipality(location) == result
    assert request.call_count == 2
    municipalities.sleep.assert_called_once_with(municipalities.RETRY_DELAY_SECONDS)


def test_expired_cache_is_refreshed_and_used_during_outage(monkeypatch):
    clock = Mock(return_value=0.0)
    monkeypatch.setattr(municipalities, "monotonic", clock)
    request = Mock(side_effect=[lookup_response(), lookup_response("120601_2")])
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = Location(longitude=19.938, latitude=50.061)
    assert municipalities.resolve_municipality(location).teryt == "1261011"

    clock.return_value = municipalities.CACHE_TTL_SECONDS + 1
    refreshed = municipalities.resolve_municipality(location)
    assert refreshed.teryt == "1206012"
    clock.return_value *= 2
    request.side_effect = TimeoutError()
    assert municipalities.resolve_municipality(location) == refreshed
    assert request.call_count == 2 + municipalities.MAX_ATTEMPTS
    assert municipalities.resolve_municipality(location) == refreshed
    assert request.call_count == 2 + 2 * municipalities.MAX_ATTEMPTS


@pytest.mark.parametrize("response", ["-1 brak wyników\n".encode(), b"0\n126101_1|City|County\n120601_2|Other|County"])
def test_expired_cache_does_not_override_missing_or_ambiguous_results(monkeypatch, response):
    clock = Mock(return_value=0.0)
    monkeypatch.setattr(municipalities, "monotonic", clock)
    request = Mock(side_effect=[lookup_response(), BytesIO(response)])
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = Location(longitude=19.938, latitude=50.061)
    municipalities.resolve_municipality(location)
    clock.return_value = municipalities.CACHE_TTL_SECONDS + 1

    if response.startswith(b"-1"):
        assert municipalities.resolve_municipality(location) is None
    else:
        with pytest.raises(municipalities.MunicipalityUnavailableError):
            municipalities.resolve_municipality(location)
    assert request.call_count == 2
    request.side_effect = TimeoutError()
    with pytest.raises(municipalities.MunicipalityUnavailableError):
        municipalities.resolve_municipality(location)


@pytest.mark.parametrize("code", [400, 403, 404])
def test_permanent_http_errors_are_not_retried(monkeypatch, code):
    request = Mock(side_effect=HTTPError("", code, "", {}, None))
    monkeypatch.setattr(municipalities, "urlopen", request)
    with pytest.raises(municipalities.MunicipalityUnavailableError):
        municipalities.resolve_municipality(Location(longitude=19.938, latitude=50.061))
    request.assert_called_once()


def test_errors_and_missing_results_are_not_cached(monkeypatch):
    request = Mock(side_effect=[BytesIO(b"invalid"), BytesIO("-1 brak wyników\n".encode()), lookup_response()])
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = Location(longitude=19.938, latitude=50.061)

    with pytest.raises(municipalities.MunicipalityUnavailableError):
        municipalities.resolve_municipality(location)
    assert municipalities.resolve_municipality(location) is None
    assert municipalities.resolve_municipality(location).teryt == "1261011"
    assert request.call_count == 3


def test_cache_evicts_least_recently_used_coordinates(monkeypatch):
    monkeypatch.setattr(municipalities, "MAX_CACHE_ENTRIES", 2)
    request = Mock(side_effect=lambda *args, **kwargs: lookup_response())
    monkeypatch.setattr(municipalities, "urlopen", request)
    locations = [Location(longitude=19 + index, latitude=50) for index in range(3)]

    for location in locations[:2]:
        municipalities.resolve_municipality(location)
    municipalities.resolve_municipality(locations[0])
    municipalities.resolve_municipality(locations[2])
    municipalities.resolve_municipality(locations[0])
    assert request.call_count == 3
    municipalities.resolve_municipality(locations[1])
    assert request.call_count == 4


def test_simultaneous_lookups_share_one_request_and_queue_other_coordinates(monkeypatch):
    release = Event()
    waiting = Event()
    lock = Lock()
    wait_count = 0
    original_result = Future.result

    def result(future, timeout=None):
        nonlocal wait_count
        if timeout == municipalities.QUEUE_TIMEOUT_SECONDS:
            with lock:
                wait_count += 1
                if wait_count == 4:
                    waiting.set()
        return original_result(future, timeout)

    monkeypatch.setattr(Future, "result", result)

    def fetch(*args, **kwargs):
        assert release.wait(5)
        return lookup_response()

    request = Mock(side_effect=fetch)
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = Location(longitude=19.938, latitude=50.061)
    other = Location(longitude=19.939, latitude=50.061)
    with ThreadPoolExecutor(max_workers=4) as executor:
        try:
            tasks = [executor.submit(municipalities.resolve_municipality, point) for point in [location] * 3 + [other]]
            assert waiting.wait(5)
            assert request.call_count == 1
        finally:
            release.set()
        assert all(task.result(timeout=5).teryt == "1261011" for task in tasks)
    assert request.call_count == 2


def test_queue_is_bounded_and_recovers_after_completion(monkeypatch):
    monkeypatch.setattr(municipalities, "MAX_PENDING_LOOKUPS", 1)
    started = Event()
    release = Event()

    def fetch(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return lookup_response()

    monkeypatch.setattr(municipalities, "urlopen", Mock(side_effect=fetch))
    location = Location(longitude=19.938, latitude=50.061)
    other = Location(longitude=19.939, latitude=50.061)
    with ThreadPoolExecutor(max_workers=1) as executor:
        task = executor.submit(municipalities.resolve_municipality, location)
        try:
            assert started.wait(5)
            with pytest.raises(municipalities.MunicipalityUnavailableError, match="queue is full"):
                municipalities.resolve_municipality(other)
        finally:
            release.set()
        task.result(timeout=5)
    assert municipalities.resolve_municipality(other).teryt == "1261011"


def test_queue_wait_is_bounded_and_lookup_can_finish_for_later_requests(monkeypatch):
    monkeypatch.setattr(municipalities, "QUEUE_TIMEOUT_SECONDS", 0.05)
    started = Event()
    release = Event()

    def fetch(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return lookup_response()

    request = Mock(side_effect=fetch)
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = Location(longitude=19.938, latitude=50.061)
    with ThreadPoolExecutor(max_workers=1) as executor:
        task = executor.submit(municipalities.resolve_municipality, location)
        try:
            assert started.wait(5)
            with pytest.raises(municipalities.MunicipalityUnavailableError, match="queue wait timed out"):
                task.result(timeout=5)
        finally:
            release.set()
    municipalities._resolver._executor.shutdown(wait=True)
    assert municipalities.resolve_municipality(location).teryt == "1261011"
    request.assert_called_once()


def test_expired_queued_lookup_does_not_contact_upstream(monkeypatch):
    clock = Mock(return_value=0.0)
    monkeypatch.setattr(municipalities, "monotonic", clock)
    started = Event()
    release = Event()
    queued = Event()
    original_result = Future.result

    def result(future, timeout=None):
        if timeout == municipalities.QUEUE_TIMEOUT_SECONDS and started.is_set():
            queued.set()
        return original_result(future, timeout)

    def fetch(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return lookup_response()

    request = Mock(side_effect=fetch)
    monkeypatch.setattr(municipalities, "urlopen", request)
    first = Location(longitude=19.938, latitude=50.061)
    second = Location(longitude=19.939, latitude=50.061)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_task = executor.submit(municipalities.resolve_municipality, first)
        try:
            assert started.wait(5)
            monkeypatch.setattr(Future, "result", result)
            second_task = executor.submit(municipalities.resolve_municipality, second)
            assert queued.wait(5)
            clock.return_value = municipalities.QUEUE_TIMEOUT_SECONDS + 1
        finally:
            release.set()
        assert first_task.result(timeout=5).teryt == "1261011"
        with pytest.raises(municipalities.MunicipalityUnavailableError, match="queue wait timed out"):
            second_task.result(timeout=5)
    request.assert_called_once()


def test_report_submission_recovers_from_timeout_and_reuses_cache(
    client, signed_in, monkeypatch, municipality_resolver
):
    user, headers = signed_in("user")
    monkeypatch.setattr(municipalities, "resolve_municipality", municipality_resolver.resolve)
    request = Mock(side_effect=[TimeoutError(), lookup_response()])
    monkeypatch.setattr(municipalities, "urlopen", request)
    location = {"longitude": 19.938, "latitude": 50.061}

    report = create_report(client, headers, location)
    assert report["municipality_teryt"] == "1261011"
    assert request.call_count == 2
    request.side_effect = TimeoutError()
    second = create_report(client, headers, location)
    assert second["municipality_teryt"] == report["municipality_teryt"]
    assert request.call_count == 2
    assert client.get("/reports", params={"user_id": user["id"]}).json()["total"] == 2


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
