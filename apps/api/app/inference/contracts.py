from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class InferenceUnavailableError(RuntimeError):
    pass


class InvalidInferenceResultError(ValueError):
    pass


class InferenceInputError(ValueError):
    pass


class TranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Text
    source_language: Text
    target_language: Text


class ChoiceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: Text
    criteria: dict[Text, Text] = Field(min_length=1)


class ImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: bytes = Field(min_length=1)
    media_type: Text


class ClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Text
    language: Text
    questions: dict[Text, ChoiceQuestion] = Field(min_length=1)
    image: ImageInput | None = None


class ChoiceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: Text
    scores: dict[Text, FiniteFloat] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["disabled", "classified"]
    answers: dict[Text, ChoiceAnswer] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_status(self) -> "ClassificationResult":
        if (self.status == "classified") != bool(self.answers):
            raise ValueError("Only a classified result can contain answers, and it must contain at least one")
        return self


class Translator(Protocol):
    def translate(self, request: TranslationRequest) -> str | None:
        """return translated text, or None when translation is disabled."""
        ...


class Classifier(Protocol):
    def classify(self, request: ClassificationRequest) -> ClassificationResult: ...


def validate_answers(request: ClassificationRequest, result: ClassificationResult) -> ClassificationResult:
    if result.status == "disabled":
        return result
    if result.answers.keys() != request.questions.keys():
        raise InvalidInferenceResultError("Classifier returned a different set of questions")
    for name, answer in result.answers.items():
        criteria = request.questions[name].criteria
        if answer.choice not in criteria or not answer.scores.keys() <= criteria.keys():
            raise InvalidInferenceResultError("Classifier returned an option outside the supplied criteria")
    return result
