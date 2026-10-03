from unittest.mock import Mock

import pytest

from app.inference.calibration import ContextCalibratedAgent
from app.inference.contracts import InvalidInferenceResultError


def prediction(probabilities):
    return {"answers": {"type": {"choice": max(probabilities, key=probabilities.get), "probabilities": probabilities}}}


def test_context_calibration_removes_category_prior_and_caches_neutral_prediction():
    agent = Mock()
    agent.predict.side_effect = [
        prediction({"a": 0.8, "b": 0.2}),
        prediction({"a": 0.6, "b": 0.4}),
        prediction({"a": 0.2, "b": 0.8}),
    ]
    calibrated = ContextCalibratedAgent(agent, strength=1)
    questions = {"type": {"type": "choice", "instructions": "Choose", "criteria": ["a", "b"]}}
    first = calibrated.predict({"description": "Report"}, questions, strict=True)
    assert first["answers"]["type"]["choice"] == "b"
    assert sum(first["answers"]["type"]["probabilities"].values()) == pytest.approx(1)
    calibrated.predict({"description": "Another report"}, questions, strict=True)
    assert agent.predict.call_count == 3
    assert agent.predict.call_args_list[0].args[0] == {"description": ""}


def test_disabled_calibration_preserves_provider_result():
    agent = Mock()
    result = ContextCalibratedAgent(agent, strength=0).predict({"description": "Text"}, {})
    assert result is agent.predict.return_value
    agent.predict.assert_called_once()


def test_image_predictions_do_not_use_text_only_priors():
    agent = Mock()
    image = object()
    result = ContextCalibratedAgent(agent, strength=1).predict({"description": "Text", "image": image}, {})
    assert result is agent.predict.return_value
    agent.predict.assert_called_once_with({"description": "Text", "image": image}, {})


@pytest.mark.parametrize("invalid", [{"a": -0.1}, {"a": float("nan")}, {"a": 0}, {"different": 1}])
def test_invalid_scores_are_rejected(invalid):
    agent = Mock()
    agent.predict.side_effect = [prediction({"a": 1}), prediction(invalid)]
    with pytest.raises(InvalidInferenceResultError):
        ContextCalibratedAgent(agent, strength=1).predict({"description": "Text"}, {})


def test_neutral_cache_is_bounded():
    agent = Mock()
    agent.predict.return_value = prediction({"a": 1})
    calibrated = ContextCalibratedAgent(agent, strength=1)
    for index in range(40):
        calibrated.predict({"description": "Text"}, {"question": index})
    assert len(calibrated._priors) == 32
