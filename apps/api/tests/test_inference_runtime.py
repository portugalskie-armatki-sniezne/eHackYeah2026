import sys
from contextlib import nullcontext
from io import BytesIO
from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.inference.contracts import (
    ClassificationRequest,
    ImageInput,
    InferenceInputError,
    InferenceUnavailableError,
    InvalidInferenceResultError,
    TranslationRequest,
)
from app.inference.runtime import (
    LocalLayaClassifier,
    LocalTranslator,
    configured_classifier,
    configured_translator,
    prepare_image,
)


def request():
    return ClassificationRequest(
        text="Problem", language="en", questions={"kind": {"instructions": "Choose", "criteria": {"a": "A"}}}
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValueError("truncated"), InferenceInputError),
        (RuntimeError("failed"), InferenceUnavailableError),
        (InvalidInferenceResultError("invalid"), InvalidInferenceResultError),
    ],
)
def test_laya_runtime_errors_have_typed_failure_modes(error, expected):
    agent = Mock()
    agent.predict.side_effect = error
    with pytest.raises(expected):
        LocalLayaClassifier(agent).classify(request())


def test_missing_configuration_does_not_load_heavy_libraries(monkeypatch):
    monkeypatch.delenv("LAYA_MODEL_PATH", raising=False)
    monkeypatch.delenv("TRANSLATION_MODEL_PATH", raising=False)
    assert configured_classifier().classify(request()).status == "disabled"
    assert configured_translator().translate(Mock()) is None


@pytest.mark.parametrize("permutations", ["zero", "0", "-1"])
def test_invalid_permutation_count_is_unavailable(monkeypatch, permutations):
    monkeypatch.setenv("LAYA_MODEL_PATH", "/unused")
    monkeypatch.setenv("LAYA_PERMUTATIONS", permutations)
    with pytest.raises(InferenceUnavailableError):
        configured_classifier()


@pytest.mark.parametrize("strength", ["nan", "-1", "1.1", "not a number"])
def test_invalid_calibration_strength_is_unavailable(monkeypatch, strength):
    monkeypatch.setenv("LAYA_MODEL_PATH", "/unused")
    monkeypatch.setenv("LAYA_CALIBRATION_STRENGTH", strength)
    with pytest.raises(InferenceUnavailableError):
        configured_classifier()


def test_incomplete_local_checkpoint_does_not_download_weights(monkeypatch, tmp_path):
    from app.inference.runtime import local_classifier

    load = Mock()
    monkeypatch.setitem(sys.modules, "laya", SimpleNamespace(load_vlm=load))
    with pytest.raises(InferenceUnavailableError):
        local_classifier(str(tmp_path), "cpu", "{}", 3, 1)
    load.assert_not_called()


def test_english_input_does_not_load_the_translation_model(monkeypatch):
    import app.inference.runtime as runtime
    from app.inference.service import EmptyClassifier, InferenceRequest, InferenceService

    load = Mock(side_effect=AssertionError("Translation must not load"))
    monkeypatch.setattr(runtime, "local_translator", load)
    monkeypatch.setenv("TRANSLATION_MODEL_PATH", "/unavailable")
    result = InferenceService(configured_translator(), EmptyClassifier()).analyze(
        InferenceRequest(text="English", source_language="en", target_language="en", questions=request().questions)
    )
    assert result.translation.status == "unchanged"
    load.assert_not_called()


def test_runtime_configuration_is_forwarded_without_fixed_model_paths(monkeypatch):
    import app.inference.runtime as runtime

    classifier = Mock()
    translator = Mock()
    monkeypatch.setattr(runtime, "local_classifier", classifier)
    monkeypatch.setattr(runtime, "local_translator", translator)
    monkeypatch.setenv("LAYA_MODEL_PATH", "/custom/classifier")
    monkeypatch.setenv("TRANSLATION_MODEL_PATH", "/custom/translator")
    monkeypatch.setenv("LAYA_DEVICE", "cpu")
    monkeypatch.setenv("LAYA_LOAD_OPTIONS", '{"max_len": 1234}')
    monkeypatch.setenv("LAYA_PERMUTATIONS", "5")
    monkeypatch.setenv("LAYA_CALIBRATION_STRENGTH", "0.5")
    monkeypatch.setenv("TRANSLATION_SOURCE_LANGUAGE", "fr")
    monkeypatch.setenv("TRANSLATION_TARGET_LANGUAGE", "en")
    classifier_provider = configured_classifier()
    translator_provider = configured_translator()
    classifier.assert_not_called()
    translator.assert_not_called()
    classifier_provider.classify(request())
    translator_provider.translate(Mock())
    classifier.assert_called_once_with("/custom/classifier", "cpu", '{"max_len": 1234}', 5, 0.5)
    translator.assert_called_once_with("/custom/translator", "fr", "en")


def test_photo_decoder_rejects_invalid_content_and_normalizes_to_rgb():
    image = pytest.importorskip("PIL.Image")
    with pytest.raises(InferenceInputError):
        prepare_image(ImageInput(data=b"\xff\xd8\xffinvalid", media_type="image/jpeg"))
    buffer = BytesIO()
    image.new("RGBA", (4, 4)).save(buffer, format="PNG")
    result = prepare_image(ImageInput(data=buffer.getvalue(), media_type="image/png"))
    assert result.mode == "RGB"
    assert result.size == (4, 4)


def test_description_labels_map_back_to_stable_enum_codes():
    agent = Mock()
    agent.predict.return_value = {"answers": {"kind": {"choice": "A", "probabilities": {"A": 1.0}}}}
    result = LocalLayaClassifier(agent, use_descriptions_as_labels=True).classify(request())
    assert agent.predict.call_args.args[1]["kind"]["criteria"] == ["A"]
    assert result.answers["kind"].choice == "a"
    assert result.answers["kind"].scores == {"a": 1.0}


def test_duplicate_display_labels_are_rejected_before_predicting():
    body = request()
    body.questions["kind"].criteria["b"] = "A"
    agent = Mock()
    with pytest.raises(InferenceInputError):
        LocalLayaClassifier(agent, use_descriptions_as_labels=True).classify(body)
    agent.predict.assert_not_called()


@pytest.fixture
def translator(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    provider = LocalTranslator.__new__(LocalTranslator)
    provider._source, provider._target = "pl", "en"
    provider._lock = Lock()
    provider._model = Mock()
    provider._model.config.max_position_embeddings = 512
    provider._model.generate.return_value = SimpleNamespace(shape=(1, 30))
    inputs = type("Inputs", (dict,), {"input_ids": SimpleNamespace(shape=(1, 20))})()
    provider._tokenizer = Mock(return_value=inputs)
    provider._tokenizer.batch_decode.return_value = ["A pothole in the road."]
    return provider


def test_translator_uses_explicit_languages_and_deterministic_generation(translator):
    result = translator.translate(
        TranslationRequest(text="Dziura w drodze.", source_language="pl", target_language="en")
    )
    assert result == "A pothole in the road."
    assert translator._tokenizer.call_args.kwargs["truncation"] is False
    translator._model.generate.assert_called_once_with(max_length=512, do_sample=False, num_beams=4)
    with pytest.raises(InferenceInputError):
        translator.translate(TranslationRequest(text="Bonjour", source_language="fr", target_language="en"))


@pytest.mark.parametrize("stage", ["input", "output"])
def test_translator_never_silently_truncates(translator, stage):
    if stage == "input":
        translator._tokenizer.return_value.input_ids.shape = (1, 513)
    else:
        translator._model.generate.return_value.shape = (1, 512)
    with pytest.raises(InferenceInputError):
        translator.translate(TranslationRequest(text="Opis", source_language="pl", target_language="en"))
    if stage == "input":
        translator._model.generate.assert_not_called()
