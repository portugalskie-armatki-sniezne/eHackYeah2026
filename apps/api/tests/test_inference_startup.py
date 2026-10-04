from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.inference import warmup as startup
from app.inference.contracts import ClassificationResult, InferenceUnavailableError
from app.inference.service import EmptyClassifier
from app.inference.translation import EmptyTranslator


def test_warmup_translates_polish_and_classifies_with_the_real_catalog(monkeypatch):
    translator = Mock()
    translator.translate.return_value = "There is a deep pothole in the road."
    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        status="classified", answers={"entity_type": {"choice": "road_manager", "scores": {"road_manager": 1.0}}}
    )
    monkeypatch.setattr(startup, "configured_translator", lambda: translator)
    monkeypatch.setattr(startup, "configured_classifier", lambda: classifier)

    startup.warmup()

    request = translator.translate.call_args.args[0]
    assert request.source_language == "pl"
    assert request.target_language == "en"
    request = classifier.classify.call_args.args[0]
    assert request.text == translator.translate.return_value
    assert request.questions["entity_type"] == startup.load_entity_question()


@pytest.mark.parametrize("disabled_provider", ["translator", "classifier"])
def test_warmup_rejects_disabled_providers(monkeypatch, disabled_provider):
    translator = Mock()
    translator.translate.return_value = "A pothole in the road."
    monkeypatch.setattr(
        startup, "configured_translator", lambda: EmptyTranslator() if disabled_provider == "translator" else translator
    )
    monkeypatch.setattr(startup, "configured_classifier", EmptyClassifier)
    with pytest.raises(InferenceUnavailableError):
        startup.warmup()


@pytest.fixture
def application(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "pool", Mock())
    monkeypatch.setattr(main, "warmup", Mock())
    monkeypatch.setattr(main.workflow_worker, "start", lambda pool: [])
    monkeypatch.delenv("INFERENCE_REQUIRED", raising=False)
    return main


def test_required_inference_is_ready_only_after_successful_warmup(application, monkeypatch):
    monkeypatch.setenv("INFERENCE_REQUIRED", "true")

    def warmup():
        assert application.app.state.ready is False

    application.warmup.side_effect = warmup
    client = TestClient(application.app)
    assert client.get("/ready").status_code == 503
    with client:
        application.warmup.assert_called_once_with()
        assert client.get("/ready").json() == {"status": "ok"}
        assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    application.pool.close.assert_called_once_with()


def test_failed_warmup_aborts_startup_and_closes_pool(application, monkeypatch):
    monkeypatch.setenv("INFERENCE_REQUIRED", "true")
    application.warmup.side_effect = InferenceUnavailableError("Model is unavailable")
    with pytest.raises(InferenceUnavailableError), TestClient(application.app):
        pytest.fail("Application must not accept traffic after a failed warmup")
    assert TestClient(application.app).get("/ready").status_code == 503
    application.pool.close.assert_called_once_with()


def test_local_startup_does_not_require_models(application):
    with TestClient(application.app) as client:
        assert client.get("/ready").status_code == 200
    application.warmup.assert_not_called()
