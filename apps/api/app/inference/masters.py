"""choose an existing master describing the same problem as a new report."""

from typing import Annotated

from fastapi import Depends

from app.inference.contracts import (
    ChoiceQuestion,
    ClassificationRequest,
    Classifier,
    InvalidInferenceResultError,
    TranslationRequest,
    Translator,
    validate_answers,
)
from app.inference.service import get_classifier, get_translator

UNMATCHED = "unmatched"
QUESTION = "Which existing report describes the same problem as this new report?"
UNMATCHED_CRITERION = "A different problem than every listed report"
# the chosen master needs this many times the score of the unmatched option, measured with
# app.inference.evaluate_masters, because without it the model merges many different problems.
MIN_SCORE_RATIO = 1.2


class MasterMatcher:
    def __init__(self, translator: Translator, classifier: Classifier) -> None:
        self._translator = translator
        self._classifier = classifier

    def _translate(self, text: str) -> str | None:
        translated = self._translator.translate(
            TranslationRequest(text=text, source_language="pl", target_language="en")
        )
        if translated is not None and (not isinstance(translated, str) or not translated.strip()):
            raise InvalidInferenceResultError("Translator returned invalid text")
        return translated

    def choose(self, title: str, candidates: dict[str, str]) -> str | None:
        """return the key of the candidate title describing the same problem, or None without a match or provider."""
        if not candidates:
            return None
        texts = [self._translate(text) for text in [title, *candidates.values()]]
        if None in texts:
            return None
        criteria = dict(zip(candidates, texts[1:], strict=True)) | {UNMATCHED: UNMATCHED_CRITERION}
        request = ClassificationRequest(
            text=texts[0], language="en", questions={"master": ChoiceQuestion(instructions=QUESTION, criteria=criteria)}
        )
        result = validate_answers(request, self._classifier.classify(request))
        if result.status != "classified":
            return None
        answer = result.answers["master"]
        if answer.choice == UNMATCHED:
            return None
        if answer.choice not in answer.scores or UNMATCHED not in answer.scores:
            raise InvalidInferenceResultError("Master matching requires scores of the choice and the unmatched option")
        if answer.scores[answer.choice] < MIN_SCORE_RATIO * answer.scores[UNMATCHED]:
            return None
        return answer.choice


def get_master_matcher(
    translator: Annotated[Translator, Depends(get_translator)],
    classifier: Annotated[Classifier, Depends(get_classifier)],
) -> MasterMatcher:
    return MasterMatcher(translator, classifier)


MasterMatch = Annotated[MasterMatcher, Depends(get_master_matcher)]
