import json
import os
from pathlib import Path
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from app.inference.contracts import ChoiceQuestion, ImageInput, InferenceUnavailableError, Text
from app.inference.service import InferenceRequest, InferenceService, TranslationResult
from app.service_entity_types import ServiceEntityType


class EntityClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[Text, Field(max_length=300)]
    description: Annotated[Text, Field(max_length=4000)]
    source_language: Literal["pl", "en"] = "pl"


class EntityClassificationResult(BaseModel):
    entity_type: ServiceEntityType
    scores: dict[ServiceEntityType, float]
    translation: TranslationResult


def load_entity_question(path: Path | None = None) -> ChoiceQuestion:
    if path is None and (configured_path := os.getenv("SERVICE_ENTITY_CRITERIA_PATH")):
        path = Path(configured_path)
    question = ChoiceQuestion.model_validate(
        json.loads((path or Path(__file__).with_name("entity_types.json")).read_text())
    )
    if set(question.criteria) != set(get_args(ServiceEntityType)):
        raise ValueError("Service entity criteria must cover exactly the FastAPI service entity enum")
    return question


class EntityClassificationService:
    def __init__(self, inference: InferenceService, question: ChoiceQuestion) -> None:
        self._inference = inference
        self._question = question

    def classify(
        self, request: EntityClassificationRequest, image: ImageInput | None = None
    ) -> EntityClassificationResult:
        result = self._inference.analyze(
            InferenceRequest(
                text=f"{request.title}\n{request.description}",
                source_language=request.source_language,
                target_language="en",
                questions={"entity_type": self._question},
            ),
            image,
        )
        if result.classification.status != "classified":
            raise InferenceUnavailableError("Service entity classification requires an enabled provider")
        answer = result.classification.answers["entity_type"]
        return EntityClassificationResult(
            entity_type=answer.choice, scores=answer.scores, translation=result.translation
        )
