from io import BytesIO
from unittest.mock import Mock

import pytest

from app.inference.contracts import (
    ClassificationRequest,
    ImageInput,
    InferenceInputError,
    InferenceUnavailableError,
    InvalidInferenceResultError,
)
from app.inference.runtime import LocalLayaClassifier, configured_classifier, configured_translator, prepare_image


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
    monkeypatch.setenv("TRANSLATION_SOURCE_LANGUAGE", "fr")
    monkeypatch.setenv("TRANSLATION_TARGET_LANGUAGE", "en")
    configured_classifier()
    configured_translator()
    classifier.assert_called_once_with("/custom/classifier", "cpu", '{"max_len": 1234}', 5)
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
