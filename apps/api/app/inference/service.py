from typing import Annotated, Literal

from fastapi import Depends
from pydantic import BaseModel, Field

from app.inference.contracts import (
    ChoiceQuestion,
    ClassificationRequest,
    ClassificationResult,
    Classifier,
    ImageInput,
    InvalidInferenceResultError,
    Text,
    TranslationRequest,
    Translator,
    validate_answers,
)


class InferenceRequest(TranslationRequest):
    questions: dict[Text, ChoiceQuestion] = Field(min_length=1)


class TranslationResult(BaseModel):
    status: Literal["disabled", "unchanged", "translated"]
    text: Text | None


class InferenceResult(BaseModel):
    translation: TranslationResult
    classification: ClassificationResult


class EmptyClassifier:
    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        return ClassificationResult(status="disabled")


class InferenceService:
    def __init__(self, translator: Translator, classifier: Classifier) -> None:
        self._translator = translator
        self._classifier = classifier

    def analyze(self, request: InferenceRequest, image: ImageInput | None = None) -> InferenceResult:
        if request.source_language == request.target_language:
            translation = TranslationResult(status="unchanged", text=request.text)
        else:
            translated = self._translator.translate(
                TranslationRequest(
                    text=request.text,
                    source_language=request.source_language,
                    target_language=request.target_language,
                )
            )
            if translated is None:
                return InferenceResult(
                    translation=TranslationResult(status="disabled", text=None),
                    classification=ClassificationResult(status="disabled"),
                )
            if not isinstance(translated, str) or not translated.strip():
                raise InvalidInferenceResultError("Translator returned invalid text")
            translation = TranslationResult(status="translated", text=translated)
        classification_request = ClassificationRequest(
            text=translation.text, language=request.target_language, questions=request.questions, image=image
        )
        result = validate_answers(classification_request, self._classifier.classify(classification_request))
        return InferenceResult(translation=translation, classification=result)


def get_translator() -> Translator:
    from app.inference.runtime import configured_translator

    return configured_translator()


def get_classifier() -> Classifier:
    from app.inference.runtime import configured_classifier

    return configured_classifier()


def get_inference_service(
    translator: Annotated[Translator, Depends(get_translator)],
    classifier: Annotated[Classifier, Depends(get_classifier)],
) -> InferenceService:
    return InferenceService(translator, classifier)


Inference = Annotated[InferenceService, Depends(get_inference_service)]
