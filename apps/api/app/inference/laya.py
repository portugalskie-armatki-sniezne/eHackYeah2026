from collections.abc import Callable, Mapping
from threading import Lock
from typing import Any, Protocol

from pydantic import ValidationError

from app.inference.contracts import (
    ChoiceAnswer,
    ClassificationRequest,
    ClassificationResult,
    ImageInput,
    InferenceInputError,
    InferenceUnavailableError,
    InvalidInferenceResultError,
    validate_answers,
)


class LayaAgent(Protocol):
    def predict(self, state: dict[str, Any], questions: dict[str, Any], **options: Any) -> dict[str, Any]: ...


class LayaClassifier:
    def __init__(
        self,
        agent: LayaAgent,
        *,
        prepare_image: Callable[[ImageInput], Any] | None = None,
        predict_options: Mapping[str, Any] | None = None,
        use_descriptions_as_labels: bool = False,
    ) -> None:
        self._agent = agent
        self._prepare_image = prepare_image
        self._predict_options = dict(predict_options or {})
        self._use_descriptions_as_labels = use_descriptions_as_labels
        self._lock = Lock()

    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        questions = {
            name: {"type": "choice", "instructions": question.instructions, "criteria": dict(question.criteria)}
            for name, question in request.questions.items()
        }
        labels = {}
        if self._use_descriptions_as_labels:
            for name, question in request.questions.items():
                labels[name] = {description: key for key, description in question.criteria.items()}
                if len(labels[name]) != len(question.criteria):
                    raise InferenceInputError("Laya option descriptions must be unique")
                questions[name]["criteria"] = list(labels[name])
        state: dict[str, Any] = {"description": request.text}
        if request.image is not None:
            if self._prepare_image is None:
                raise InferenceUnavailableError("Laya image preparation is not configured")
            state["image"] = self._prepare_image(request.image)
        with self._lock:
            prediction = self._agent.predict(state, questions, **self._predict_options)
        try:
            result = ClassificationResult(
                status="classified",
                answers={
                    name: ChoiceAnswer(
                        choice=labels[name][answer["choice"]] if labels else answer["choice"],
                        scores={labels[name][key]: value for key, value in answer["probabilities"].items()}
                        if labels
                        else answer["probabilities"],
                    )
                    for name, answer in prediction["answers"].items()
                },
            )
        except (KeyError, TypeError, AttributeError, ValidationError) as error:
            raise InvalidInferenceResultError("Laya returned an invalid prediction") from error
        return validate_answers(request, result)
