import json
import math
from collections import OrderedDict
from typing import Any

from app.inference.contracts import InvalidInferenceResultError
from app.inference.laya import LayaAgent


class ContextCalibratedAgent:
    def __init__(self, agent: LayaAgent, strength: float) -> None:
        self._agent = agent
        self._strength = strength
        self._priors: OrderedDict[str, dict] = OrderedDict()

    def predict(self, state: dict[str, Any], questions: dict[str, Any], **options: Any) -> dict[str, Any]:
        # text-only priors do not describe the model's behavior with an image.
        if not self._strength or "image" in state:
            return self._agent.predict(state, questions, **options)
        key = json.dumps([questions, options], ensure_ascii=False)
        if key not in self._priors:
            self._priors[key] = self._agent.predict({"description": ""}, questions, **options)
            if len(self._priors) > 32:
                self._priors.popitem(last=False)
        prediction = self._agent.predict(state, questions, **options)
        try:
            answers = {}
            for name, answer in prediction["answers"].items():
                probabilities = answer["probabilities"]
                prior = self._priors[key]["answers"][name]["probabilities"]
                if not probabilities or prior.keys() != probabilities.keys():
                    raise ValueError("Calibration options differ")
                if any(
                    not math.isfinite(value) or not 0 <= value <= 1
                    for value in [*prior.values(), *probabilities.values()]
                ):
                    raise ValueError("Invalid probability")
                adjusted = {
                    label: probability / max(prior[label], 1e-6) ** self._strength
                    for label, probability in probabilities.items()
                }
                total = sum(adjusted.values())
                answers[name] = {
                    "choice": max(adjusted, key=adjusted.get),
                    "probabilities": {label: value / total for label, value in adjusted.items()},
                }
            return {**prediction, "answers": answers}
        except (KeyError, TypeError, AttributeError, ValueError, ZeroDivisionError) as error:
            raise InvalidInferenceResultError("Laya returned invalid calibration scores") from error
