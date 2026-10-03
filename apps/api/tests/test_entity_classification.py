import json
from pathlib import Path
from typing import get_args
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import get_current_user
from app.inference.contracts import (
    ChoiceAnswer,
    ClassificationResult,
    ImageInput,
    InferenceInputError,
    InferenceUnavailableError,
    InvalidInferenceResultError,
)
from app.inference.entities import EntityClassificationRequest, EntityClassificationService, load_entity_question
from app.inference.service import EmptyClassifier, InferenceService, get_classifier, get_translator
from app.inference.translation import CallableTranslator, EmptyTranslator
from app.main import app
from app.service_entities import ServiceEntityType

TYPES = get_args(ServiceEntityType)
PAYLOAD = {"title": "Dziura w drodze", "description": "W jezdni jest głęboka dziura.", "source_language": "pl"}


def classifier_returning(entity_type):
    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        status="classified", answers={"entity_type": ChoiceAnswer(choice=entity_type, scores={entity_type: 0.1})}
    )
    return classifier


def test_criteria_and_realistic_dataset_cover_the_authoritative_api_enum():
    assert set(load_entity_question().criteria) == set(TYPES)
    cases = json.loads((Path(__file__).parents[3] / "tests/fixtures/entity_classification.json").read_text())
    assert len({case["id"] for case in cases}) == len(cases)
    for split in ("development", "holdout"):
        assert {case["expected"] for case in cases if case["split"] == split} == set(TYPES)
    assert all(case["expected"] is None or case["expected"] in TYPES for case in cases)
    for case in cases:
        EntityClassificationRequest.model_validate({key: case[key] for key in PAYLOAD})


@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_custom_criteria_must_exactly_match_enum(tmp_path, mutation):
    question = load_entity_question().model_dump()
    if mutation == "missing":
        question["criteria"].pop(TYPES[0])
    else:
        question["criteria"]["unknown"] = "No match"
    path = tmp_path / "criteria.json"
    path.write_text(json.dumps(question))
    with pytest.raises(ValueError, match="exactly"):
        load_entity_question(path)


@pytest.mark.parametrize("entity_type", TYPES)
def test_every_enum_value_is_returned_even_with_low_score(entity_type):
    classifier = classifier_returning(entity_type)
    service = EntityClassificationService(InferenceService(EmptyTranslator(), classifier), load_entity_question())
    result = service.classify(EntityClassificationRequest(**(PAYLOAD | {"source_language": "en"})))
    assert result.entity_type == entity_type
    assert result.scores == {entity_type: 0.1}
    assert result.translation.status == "unchanged"


def test_title_and_description_are_translated_together_and_photo_reaches_classifier():
    translate = Mock(return_value="Pothole in road. A deep hole in the road surface.")
    classifier = classifier_returning("road_manager")
    service = EntityClassificationService(
        InferenceService(CallableTranslator(translate), classifier), load_entity_question()
    )
    image = ImageInput(data=b"photo bytes", media_type="image/jpeg")
    result = service.classify(EntityClassificationRequest(**PAYLOAD), image)
    assert translate.call_args.args[0].text == PAYLOAD["title"] + "\n" + PAYLOAD["description"]
    request = classifier.classify.call_args.args[0]
    assert request.text == translate.return_value
    assert request.language == "en"
    assert request.image == image
    assert set(request.questions["entity_type"].criteria) == set(TYPES)
    assert result.entity_type == "road_manager"


@pytest.mark.parametrize("language", ["pl", "en"])
def test_disabled_providers_do_not_invent_an_enum_value(language):
    service = EntityClassificationService(
        InferenceService(EmptyTranslator(), EmptyClassifier()), load_entity_question()
    )
    with pytest.raises(InferenceUnavailableError):
        service.classify(EntityClassificationRequest(**(PAYLOAD | {"source_language": language})))


@pytest.mark.parametrize("choice", ["unknown", "road_manager,municipal_guard", "ROAD_MANAGER"])
def test_out_of_enum_results_are_rejected(choice):
    service = EntityClassificationService(
        InferenceService(EmptyTranslator(), classifier_returning(choice)), load_entity_question()
    )
    with pytest.raises(InvalidInferenceResultError):
        service.classify(EntityClassificationRequest(**(PAYLOAD | {"source_language": "en"})))


@pytest.mark.parametrize(
    "change",
    [{"title": " "}, {"description": ""}, {"description": "x" * 4001}, {"source_language": "de"}, {"questions": {}}],
)
def test_request_rejects_empty_text_oversize_and_client_supplied_options(change):
    with pytest.raises(ValidationError):
        EntityClassificationRequest.model_validate(PAYLOAD | change)


@pytest.fixture
def client(monkeypatch):
    for name in ("LAYA_MODEL_PATH", "TRANSLATION_MODEL_PATH", "SERVICE_ENTITY_CRITERIA_PATH"):
        monkeypatch.delenv(name, raising=False)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[get_translator] = lambda: CallableTranslator(lambda _: "A pothole in the road")
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


@pytest.mark.parametrize("photo", [False, True])
def test_endpoint_returns_single_typed_value_with_optional_photo(client, photo):
    classifier = classifier_returning("road_manager")
    app.dependency_overrides[get_classifier] = lambda: classifier
    image_bytes = (Path(__file__).parents[3] / "tooling/seed/mock_photos/pothole.jpg").read_bytes()
    files = {"image": ("pothole.jpg", image_bytes, "image/jpeg")} if photo else None
    response = client.post("/inference/service-entity", data={"payload": json.dumps(PAYLOAD)}, files=files)
    assert response.status_code == 200
    assert response.json()["entity_type"] == "road_manager"
    assert (classifier.classify.call_args.args[0].image is not None) == photo


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (InferenceUnavailableError("private"), 503),
        (InvalidInferenceResultError("private"), 502),
        (InferenceInputError("private"), 422),
    ],
)
def test_errors_in_dependencies_and_predictions_are_safe(client, error, status):
    def fail():
        raise error

    app.dependency_overrides[get_classifier] = fail
    response = client.post("/inference/service-entity", data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == status
    assert "private" not in response.text


def test_unconfigured_endpoint_returns_unavailable(client):
    assert client.post("/inference/service-entity", data={"payload": json.dumps(PAYLOAD)}).status_code == 503


def test_custom_configuration_is_validated_at_endpoint(client, monkeypatch, tmp_path):
    path = tmp_path / "question.json"
    path.write_text('{"criteria": {"unknown": "Unknown"}, "instructions": "Choose"}')
    monkeypatch.setenv("SERVICE_ENTITY_CRITERIA_PATH", str(path))
    assert client.post("/inference/service-entity", data={"payload": json.dumps(PAYLOAD)}).status_code == 503


def test_authentication_and_openapi_enum():
    assert TestClient(app).post("/inference/service-entity", data={"payload": json.dumps(PAYLOAD)}).status_code == 401
    schema = app.openapi()["components"]["schemas"]["EntityClassificationResult"]
    assert set(schema["properties"]["entity_type"]["enum"]) == set(TYPES)
