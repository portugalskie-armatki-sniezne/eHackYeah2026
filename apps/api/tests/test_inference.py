import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import storage
from app.auth import get_current_user
from app.inference.contracts import (
    ChoiceAnswer,
    ClassificationRequest,
    ClassificationResult,
    ImageInput,
    InferenceUnavailableError,
    InvalidInferenceResultError,
    TranslationRequest,
)
from app.inference.laya import LayaClassifier
from app.inference.service import (
    EmptyClassifier,
    InferenceRequest,
    InferenceService,
    get_classifier,
    get_translator,
)
from app.inference.translation import CallableTranslator, EmptyTranslator
from app.main import app

PAYLOAD = {
    "text": "Opis do analizy.",
    "source_language": "pl",
    "target_language": "en",
    "questions": {
        "destination": {
            "instructions": "Choose the best destination.",
            "criteria": {"candidate-a": "First destination", "candidate-b": "Second destination"},
        },
        "priority": {
            "instructions": "Choose the priority.",
            "criteria": {"low": "Low priority", "high": "High priority"},
        },
    },
}
IMAGE = ImageInput(data=b"\xff\xd8\xff\xe0" + b"\0" * 16, media_type="image/jpeg")


def classified() -> ClassificationResult:
    return ClassificationResult(
        status="classified",
        answers={
            "destination": ChoiceAnswer(choice="candidate-b", scores={"candidate-a": 0.1, "candidate-b": 0.9}),
            "priority": ChoiceAnswer(choice="low"),
        },
    )


def test_translation_precedes_classification_and_preserves_questions_and_photo():
    calls = []

    def translate(request: TranslationRequest) -> str:
        calls.append("translation")
        assert request.text == PAYLOAD["text"]
        assert (request.source_language, request.target_language) == ("pl", "en")
        return "Description for analysis."

    def classify(request: ClassificationRequest) -> ClassificationResult:
        calls.append("classification")
        assert request.text == "Description for analysis."
        assert request.language == "en"
        assert request.questions["destination"].criteria == PAYLOAD["questions"]["destination"]["criteria"]
        assert request.image == IMAGE
        return classified()

    classifier = Mock()
    classifier.classify.side_effect = classify
    request = InferenceRequest.model_validate(PAYLOAD)
    result = InferenceService(CallableTranslator(translate), classifier).analyze(request, IMAGE)
    assert calls == ["translation", "classification"]
    assert result.translation.status == "translated"
    assert result.classification == classified()
    assert request.text == PAYLOAD["text"]


def test_disabled_translation_does_not_send_untranslated_text_to_classifier():
    classifier = Mock()
    result = InferenceService(EmptyTranslator(), classifier).analyze(InferenceRequest.model_validate(PAYLOAD), IMAGE)
    assert result.translation.status == "disabled"
    assert result.translation.text is None
    assert result.classification.status == "disabled"
    assert result.classification.answers == {}
    classifier.classify.assert_not_called()


def test_matching_languages_skip_translator_and_allow_text_without_photo():
    translator = Mock()
    classifier = Mock()
    classifier.classify.return_value = classified()
    request = InferenceRequest.model_validate(PAYLOAD | {"target_language": "pl"})
    result = InferenceService(translator, classifier).analyze(request)
    assert result.translation.status == "unchanged"
    assert result.translation.text == request.text
    translator.translate.assert_not_called()
    assert classifier.classify.call_args.args[0].image is None


@pytest.mark.parametrize("text", ["", "  ", 123])
def test_invalid_translation_is_rejected_before_classification(text):
    classifier = Mock()
    translator = CallableTranslator(Mock(return_value=text))
    with pytest.raises(InvalidInferenceResultError):
        InferenceService(translator, classifier).analyze(InferenceRequest.model_validate(PAYLOAD))
    classifier.classify.assert_not_called()


def test_laya_uses_supplied_agent_questions_options_and_image_preparation():
    agent = Mock()
    agent.predict.return_value = {
        "answers": {
            "destination": {"choice": "candidate-b", "probabilities": {"candidate-a": 0.1, "candidate-b": 0.9}},
            "priority": {"choice": "low", "probabilities": {"low": 0.7, "high": 0.3}},
        }
    }
    prepared_image = object()
    prepare_image = Mock(return_value=prepared_image)
    classifier = LayaClassifier(
        agent, prepare_image=prepare_image, predict_options={"strict": True, "n_permutations": 2}
    )
    request = ClassificationRequest(text="Any text", language="en", questions=PAYLOAD["questions"], image=IMAGE)
    result = classifier.classify(request)
    state, questions = agent.predict.call_args.args
    assert state == {"description": request.text, "image": prepared_image}
    assert questions == {name: {"type": "choice", **question} for name, question in PAYLOAD["questions"].items()}
    assert agent.predict.call_args.kwargs == {"strict": True, "n_permutations": 2}
    prepare_image.assert_called_once_with(IMAGE)
    assert result.answers["destination"] == classified().answers["destination"]


def test_laya_text_only_does_not_require_image_preparation():
    agent = Mock()
    agent.predict.return_value = {"answers": {"custom": {"choice": "yes", "probabilities": {"yes": 1}}}}
    request = ClassificationRequest(
        text="Any text", language="en", questions={"custom": {"instructions": "Choose", "criteria": {"yes": "Yes"}}}
    )
    assert LayaClassifier(agent).classify(request).answers["custom"].choice == "yes"
    assert agent.predict.call_args.args[0] == {"description": "Any text"}
    assert agent.predict.call_args.kwargs == {}


def test_laya_requires_image_preparation_when_photo_is_supplied():
    agent = Mock()
    request = ClassificationRequest(text="Text", language="en", questions=PAYLOAD["questions"], image=IMAGE)
    with pytest.raises(InferenceUnavailableError):
        LayaClassifier(agent).classify(request)
    agent.predict.assert_not_called()


@pytest.mark.parametrize(
    "prediction",
    [
        {},
        {"answers": []},
        {"answers": {}},
        {"answers": {"custom": {"choice": "yes"}}},
        {"answers": {"custom": {"choice": "outside", "probabilities": {}}}},
        {"answers": {"custom": {"choice": "yes", "probabilities": {"outside": 1}}}},
        {"answers": {"custom": {"choice": "yes", "probabilities": {"yes": float("nan")}}}},
        {"answers": {"different": {"choice": "yes", "probabilities": {}}}},
    ],
)
def test_laya_rejects_malformed_and_out_of_catalog_predictions(prediction):
    agent = Mock()
    agent.predict.return_value = prediction
    request = ClassificationRequest(
        text="Text", language="en", questions={"custom": {"instructions": "Choose", "criteria": {"yes": "Yes"}}}
    )
    with pytest.raises(InvalidInferenceResultError):
        LayaClassifier(agent).classify(request)


def test_custom_classifier_is_also_checked_against_supplied_criteria():
    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        status="classified", answers={"unexpected": ChoiceAnswer(choice="unexpected")}
    )
    with pytest.raises(InvalidInferenceResultError):
        InferenceService(EmptyTranslator(), classifier).analyze(
            InferenceRequest.model_validate(PAYLOAD | {"target_language": "pl"})
        )


@pytest.mark.parametrize("changes", [{"text": " "}, {"source_language": ""}, {"questions": {}}, {"unknown": True}])
def test_request_rejects_missing_content_and_unknown_fields(changes):
    with pytest.raises(ValidationError):
        InferenceRequest.model_validate(PAYLOAD | changes)


@pytest.fixture
def inference_client(monkeypatch):
    monkeypatch.delenv("LAYA_MODEL_PATH", raising=False)
    monkeypatch.delenv("TRANSLATION_MODEL_PATH", raising=False)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


@pytest.mark.parametrize("with_photo", [False, True])
def test_api_defaults_are_disabled_with_or_without_photo(inference_client, with_photo):
    files = {"image": ("photo.jpg", IMAGE.data, IMAGE.media_type)} if with_photo else None
    response = inference_client.post("/inference", data={"payload": json.dumps(PAYLOAD)}, files=files)
    assert response.status_code == 200
    assert response.json() == {
        "translation": {"status": "disabled", "text": None},
        "classification": {"status": "disabled", "answers": {}},
    }


def test_api_dependencies_can_be_replaced_and_photo_type_is_detected_from_content(inference_client):
    translate = Mock(return_value="Translated text")
    classifier = Mock()
    classifier.classify.return_value = classified()
    app.dependency_overrides[get_translator] = lambda: CallableTranslator(translate)
    app.dependency_overrides[get_classifier] = lambda: classifier
    response = inference_client.post(
        "/inference", data={"payload": json.dumps(PAYLOAD)}, files={"image": ("wrong.txt", IMAGE.data, "text/plain")}
    )
    assert response.status_code == 200
    assert response.json()["classification"] == classified().model_dump()
    assert classifier.classify.call_args.args[0].image == IMAGE


@pytest.mark.parametrize("payload", ["not json", "{}", json.dumps(PAYLOAD | {"questions": {}})])
def test_api_rejects_invalid_payload(inference_client, payload):
    assert inference_client.post("/inference", data={"payload": payload}).status_code == 422


def test_api_rejects_unsupported_and_oversized_photos(inference_client, monkeypatch):
    form = {"payload": json.dumps(PAYLOAD)}
    assert (
        inference_client.post("/inference", data=form, files={"image": ("photo.jpg", b"not an image")}).status_code
        == 422
    )
    monkeypatch.setattr(storage, "MAX_PHOTO_BYTES", len(IMAGE.data) - 1)
    assert inference_client.post("/inference", data=form, files={"image": ("photo.jpg", IMAGE.data)}).status_code == 413


@pytest.mark.parametrize(
    ("error", "expected"),
    [(InferenceUnavailableError("private details"), 503), (InvalidInferenceResultError("details"), 502)],
)
def test_api_provider_errors_have_explicit_status_and_do_not_expose_details(inference_client, error, expected):
    translator = CallableTranslator(Mock(side_effect=error))
    app.dependency_overrides[get_translator] = lambda: translator
    response = inference_client.post("/inference", data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == expected
    assert "details" not in response.text


def test_api_requires_authentication():
    response = TestClient(app).post("/inference", data={"payload": json.dumps(PAYLOAD)})
    assert response.status_code == 401


def test_empty_classifier_can_be_used_independently():
    request = ClassificationRequest(text="Text", language="any", questions=PAYLOAD["questions"], image=IMAGE)
    assert EmptyClassifier().classify(request) == ClassificationResult(status="disabled")
