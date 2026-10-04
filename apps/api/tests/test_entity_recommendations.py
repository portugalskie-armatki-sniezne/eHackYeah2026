import json
from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import geocoding, municipalities
from app.common import Location
from app.inference.contracts import ChoiceAnswer, ClassificationResult, InferenceUnavailableError
from app.inference.recommendations import Candidate, choose_candidate
from app.inference.service import get_classifier, get_translator
from app.inference.translation import CallableTranslator
from app.main import app
from app.service_entities import ServiceEntity
from conftest import JPEG

URL = "/inference/service-entity/recommendation"
PAYLOAD = {
    "title": "Dziura w jezdni",
    "description": "Głęboka dziura na drodze.",
    "location": {"longitude": 19.938, "latitude": 50.061},
}


def entity(identifier=1, entity_type="road_manager"):
    values = dict.fromkeys(ServiceEntity.model_fields)
    values.update(
        id=identifier,
        is_active=True,
        source_key=f"test:{identifier}",
        name="Jednostka",
        entity_type=entity_type,
        locality="Kraków",
        street="Centralna",
        house_number="53",
        source_urls=["https://example.com"],
        verified_on=date(2026, 10, 3),
    )
    return ServiceEntity.model_validate(values)


def candidate(identifier, teryt, distance, entity_type="road_manager"):
    return Candidate(
        entity(identifier, entity_type),
        Location(**PAYLOAD["location"]),
        teryt,
        distance,
    )


@pytest.mark.parametrize(
    "candidates, expected_id, expected_level",
    [
        ([candidate(1, "1206012", 1000), candidate(2, "1206022", 1)], 1, "municipality"),
        ([candidate(1, "1206022", 1000), candidate(2, "1207011", 1)], 1, "county"),
        ([candidate(1, "1207011", 1000), candidate(2, "2401011", 1)], 1, "province"),
        ([candidate(1, "2401011", 1000), candidate(2, "0201011", 1)], 2, "nearest"),
        ([candidate(1, "1206012", 1000), candidate(2, "1206012", 1)], 2, "municipality"),
        ([candidate(2, "1206012", 1), candidate(1, "1206012", 1)], 1, "municipality"),
        ([candidate(1, "1206012", 1, "municipal_guard"), candidate(2, "2401011", 1000)], 2, "nearest"),
    ],
)
def test_administrative_priority_then_distance_then_stable_id(candidates, expected_id, expected_level):
    result = choose_candidate(candidates, "road_manager", "1206012")
    assert result.entity.id == expected_id
    assert result.match_level == expected_level


def test_no_candidate_of_selected_type_does_not_fall_back_to_another_type():
    assert choose_candidate([candidate(1, "1206012", 1, "municipal_guard")], "road_manager", "1206012") is None
    assert choose_candidate([], "road_manager", "1206012") is None


@pytest.fixture
def recommendation_setup(client, connection, signed_in, monkeypatch):
    _, headers = signed_in()
    connection.execute("DELETE FROM service_entities WHERE entity_type = 'road_manager'")
    ids = []
    for index, number in enumerate(("53", "54", None)):
        row = connection.execute(
            "INSERT INTO service_entities (source_key, name, entity_type, locality, street, house_number, "
            "teryt_code, source_urls, verified_on) VALUES (%s, %s, 'road_manager', 'Kraków', 'Centralna', %s, "
            "'0201011', ARRAY['https://example.com'], '2026-10-03') RETURNING id",
            (f"test:{uuid4()}", f"Testowa jednostka {index}", number),
        ).fetchone()
        ids.append(row["id"])
    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        status="classified", answers={"entity_type": ChoiceAnswer(choice="road_manager", scores={"road_manager": 0.7})}
    )
    app.dependency_overrides[get_classifier] = lambda: classifier
    app.dependency_overrides[get_translator] = lambda: CallableTranslator(lambda _: "A pothole in the road")
    monkeypatch.delenv("SERVICE_ENTITY_CRITERIA_PATH", raising=False)
    connection.execute(
        "UPDATE service_entities SET seat_location = "
        "ST_Transform(ST_SetSRID(ST_MakePoint(572085.53 + CASE WHEN house_number = '54' THEN 1000 ELSE 0 END, "
        "244516.83), 2180), 4326)::geography, seat_teryt = '1261011', "
        "seat_geocoded_at = CURRENT_TIMESTAMP, seat_address = jsonb_build_array(locality, street, house_number) "
        "WHERE id = ANY(%s) AND house_number IS NOT NULL",
        (ids,),
    )
    lookup = Mock(side_effect=AssertionError("recommendations must not geocode institution seats"))
    monkeypatch.setattr(geocoding, "address_point", lookup)
    return headers, ids, classifier, lookup


@pytest.mark.parametrize("photo", [False, True])
def test_endpoint_recommends_from_fresh_coordinates_without_writing_reports(
    client,
    connection,
    recommendation_setup,
    photo,
):
    headers, ids, classifier, lookup = recommendation_setup
    before = connection.execute(
        "SELECT (SELECT count(*) FROM reports) AS reports, count(*) AS masters FROM master_reports"
    ).fetchone()
    result = client.post(
        URL,
        headers=headers,
        data={"payload": json.dumps(PAYLOAD)},
        files={"image": ("photo.jpg", JPEG, "image/jpeg")} if photo else None,
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["entity_type"] == "road_manager"
    assert body["region"]["municipality_teryt"] == "1261011"
    assert body["region"]["province_teryt"] == "12"
    assert body["recommendation"]["entity"]["id"] == ids[0]
    assert body["recommendation"]["seat_municipality_teryt"] == "1261011"
    assert body["recommendation"]["match_level"] == "municipality"
    assert body["recommendation"]["distance_m"] > 0
    assert body["recommendation"]["seat_location"]["longitude"] == pytest.approx(20.006, abs=0.01)
    assert body["recommendation"]["seat_location"]["latitude"] == pytest.approx(50.064, abs=0.01)
    assert body["candidates_count"] == 3
    assert body["skipped_candidates_count"] == 1
    lookup.assert_not_called()
    assert (classifier.classify.call_args.args[0].image is not None) == photo
    assert (
        connection.execute(
            "SELECT (SELECT count(*) FROM reports) AS reports, count(*) AS masters FROM master_reports"
        ).fetchone()
        == before
    )


def test_no_geocoded_seat_returns_explicit_no_recommendation(client, connection, recommendation_setup):
    headers, _, _, _ = recommendation_setup
    connection.execute(
        "UPDATE service_entities SET seat_location = NULL, seat_teryt = NULL, "
        "seat_geocoded_at = NULL, seat_address = NULL"
    )
    response = client.post(URL, headers=headers, data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == 200
    assert response.json()["recommendation"] is None
    assert response.json()["skipped_candidates_count"] == 3


def test_no_entities_does_not_geocode_or_change_type(client, connection, recommendation_setup):
    headers, _, _, lookup = recommendation_setup
    connection.execute("DELETE FROM service_entities WHERE entity_type = 'road_manager'")
    response = client.post(URL, headers=headers, data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == 200
    assert response.json()["recommendation"] is None
    assert response.json()["candidates_count"] == 0
    assert response.json()["entity_type"] == "road_manager"
    lookup.assert_not_called()


def test_inactive_institution_remains_in_catalog_but_is_not_recommended(client, connection, recommendation_setup):
    headers, ids, _, _ = recommendation_setup
    connection.execute("UPDATE service_entities SET is_active = FALSE WHERE id = %s", (ids[0],))
    assert client.get(f"/service-entities/{ids[0]}").json()["is_active"] is False
    result = client.post(URL, headers=headers, data={"payload": json.dumps(PAYLOAD)}).json()
    assert result["recommendation"]["entity"]["id"] == ids[1]
    assert result["skipped_candidates_count"] == 2


def test_changed_seat_address_is_excluded_until_geocoded_again(client, connection, recommendation_setup):
    headers, ids, _, lookup = recommendation_setup
    connection.execute("UPDATE service_entities SET house_number = '99' WHERE id = %s", (ids[0],))
    response = client.post(URL, headers=headers, data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == 200
    assert response.json()["recommendation"]["entity"]["id"] == ids[1]
    assert response.json()["skipped_candidates_count"] == 2
    lookup.assert_not_called()


@pytest.mark.parametrize("location", [None, {"longitude": 181, "latitude": 50}, {"latitude": 50}])
def test_invalid_location_never_classifies(client, recommendation_setup, location):
    headers, _, classifier, _ = recommendation_setup
    response = client.post(URL, headers=headers, data={"payload": json.dumps(PAYLOAD | {"location": location})})
    assert response.status_code == 422
    classifier.classify.assert_not_called()


def test_report_outside_supported_region_never_classifies(client, recommendation_setup, monkeypatch):
    headers, _, classifier, _ = recommendation_setup
    monkeypatch.setattr(
        municipalities, "resolve_municipality", lambda _: municipalities.Municipality("0201011", "X", "Y")
    )
    response = client.post(URL, headers=headers, data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == 422
    classifier.classify.assert_not_called()


def test_disabled_classifier_does_not_geocode_seats(client, recommendation_setup):
    headers, _, classifier, lookup = recommendation_setup
    classifier.classify.side_effect = InferenceUnavailableError
    response = client.post(URL, headers=headers, data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == 503
    lookup.assert_not_called()


def test_recommendation_requires_authentication():
    assert TestClient(app).post(URL, data={"payload": json.dumps(PAYLOAD)}).status_code == 401
