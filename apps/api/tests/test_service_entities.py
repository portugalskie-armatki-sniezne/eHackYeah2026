from datetime import date
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def entities(connection: psycopg.Connection):
    token = uuid4().hex
    rows = []
    for index, (entity_type, teryt_code, locality) in enumerate(
        [
            ("road_manager", "1261011", "Kraków"),
            ("transport_operator", "1261011", "Kraków"),
            ("road_manager", None, "Tarnów"),
        ]
    ):
        rows.append(
            connection.execute(
                "INSERT INTO service_entities "
                "(source_key, name, short_name, entity_type, teryt_code, locality, "
                "reporting_channel, reporting_channel_description, source_urls, verified_on) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (
                    f"test:{token}:{index}",
                    f"Jednostka {token} {index}",
                    f"Skrót 100%_\\{token}" if index == 0 else None,
                    entity_type,
                    teryt_code,
                    locality,
                    "mailto:reports@example.com" if index == 0 else None,
                    "Zgłoszenia usterek" if index == 0 else None,
                    ["https://example.com/bip"],
                    date(2026, 10, 3),
                ),
            ).fetchone()
        )
    return rows


def test_service_entity_details_are_public(client: TestClient, entities):
    for row in entities:
        response = client.get(f"/service-entities/{row['id']}")
        assert response.status_code == 200
        assert response.json() == row | {"verified_on": "2026-10-03"}
    assert client.get("/service-entities/0").status_code == 404
    assert client.get("/service-entities/not-an-id").status_code == 422


def test_service_entity_filters_and_pagination(client: TestClient, entities):
    token = entities[0]["source_key"].split(":")[1]
    query = {"q": token.upper()}
    page = client.get("/service-entities", params=query | {"limit": 1, "offset": 1}).json()
    assert page["total"] == 3
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert [item["id"] for item in page["items"]] == [entities[1]["id"]]

    filters = [
        ({"entity_type": "road_manager"}, [entities[0], entities[2]]),
        ({"teryt_code": "1261011"}, entities[:2]),
        ({"locality": "Tarnów"}, [entities[2]]),
        ({"entity_type": "road_manager", "teryt_code": "1261011", "locality": "Kraków"}, [entities[0]]),
        ({"locality": "Krak"}, []),
    ]
    for filters_query, expected in filters:
        response = client.get("/service-entities", params=query | filters_query)
        assert response.status_code == 200
        assert response.json()["total"] == len(expected)
        assert [item["id"] for item in response.json()["items"]] == [row["id"] for row in expected]

    page = client.get("/service-entities", params=query | {"offset": 3}).json()
    assert page["total"] == 3
    assert page["items"] == []


def test_service_entity_search_matches_short_name_and_literal_characters(client: TestClient, entities):
    response = client.get("/service-entities", params={"q": entities[0]["short_name"].upper()})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [entities[0]["id"]]
    for query in ("100__", "' OR 1=1 --"):
        page = client.get("/service-entities", params={"q": query}).json()
        assert page["total"] == 0
        assert page["items"] == []


@pytest.mark.parametrize("params", [{"entity_type": "unknown"}, {"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_service_entity_invalid_filters(client: TestClient, params):
    assert client.get("/service-entities", params=params).status_code == 422


def test_service_entity_openapi_describes_filters(client: TestClient):
    schema = client.get("/openapi.json").json()
    parameters = {item["name"]: item for item in schema["paths"]["/service-entities"]["get"]["parameters"]}
    assert all(parameter.get("description") for parameter in parameters.values())
    types = parameters["entity_type"]["schema"]["anyOf"][0]["enum"]
    assert len(types) == 15
    assert "road_manager" in types
    assert parameters["limit"]["schema"]["maximum"] == 200
    assert parameters["offset"]["schema"]["minimum"] == 0
