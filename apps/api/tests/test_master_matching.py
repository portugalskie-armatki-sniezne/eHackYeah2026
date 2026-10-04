import json
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import matching
from app.common import Location
from app.inference.contracts import (
    ChoiceAnswer,
    ClassificationRequest,
    ClassificationResult,
    InferenceUnavailableError,
    InvalidInferenceResultError,
)
from app.inference.masters import UNMATCHED, MasterMatcher, get_master_matcher
from app.inference.service import EmptyClassifier
from app.inference.translation import CallableTranslator, EmptyTranslator
from app.main import app
from conftest import create_report, moved, random_location, reference_id

ORIGINAL = "Jakiś gość tutaj się pałęta niebezpieczny"
REWORDED = "Niebezpiecznie zachowujący się mieszkaniec w okolicy"


class Classifier:
    """choose the candidate whose translated title is in the report text, with the given scores."""

    def __init__(self, choice_score: float = 0.75, unmatched_score: float = 0.25, error: Exception | None = None):
        self.requests: list[ClassificationRequest] = []
        self._scores = choice_score, unmatched_score
        self._error = error

    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        criteria = request.questions["master"].criteria
        choice = next((key for key, text in criteria.items() if text in request.text), UNMATCHED)
        scores = {key: 0.0 for key in criteria} | {choice: self._scores[0]}
        if choice != UNMATCHED:
            scores[UNMATCHED] = self._scores[1]
        return ClassificationResult(status="classified", answers={"master": ChoiceAnswer(choice=choice, scores=scores)})


# the fake translator maps both titles of the same problem to one text.
TRANSLATIONS = {ORIGINAL: "dangerous man", REWORDED: "a dangerous man nearby", "Zepsuta latarnia": "broken lamp"}
translator = CallableTranslator(lambda request: TRANSLATIONS.get(request.text, request.text))


@pytest.fixture
def use_matcher(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def use(classifier: Classifier) -> Classifier:
        monkeypatch.setitem(app.dependency_overrides, get_master_matcher, lambda: MasterMatcher(translator, classifier))
        return classifier

    return use


def test_matcher_asks_about_translated_candidates():
    classifier = Classifier()

    assert MasterMatcher(translator, classifier).choose(REWORDED, {"first": ORIGINAL}) == "first"
    request = classifier.requests[0]
    assert (request.text, request.language) == ("a dangerous man nearby", "en")
    assert set(request.questions["master"].criteria) == {"first", UNMATCHED}
    assert request.questions["master"].criteria["first"] == "dangerous man"


@pytest.mark.parametrize(
    "classifier, expected",
    [
        (Classifier(0.55, 0.45), "first"),
        (Classifier(0.52, 0.48), None),
        (EmptyClassifier(), None),
    ],
)
def test_matcher_requires_a_clear_lead_over_unmatched(classifier, expected):
    assert MasterMatcher(translator, classifier).choose(REWORDED, {"first": ORIGINAL}) == expected


def test_matcher_skips_classifier_without_translator():
    classifier = Classifier()

    assert MasterMatcher(EmptyTranslator(), classifier).choose(REWORDED, {"first": ORIGINAL}) is None
    assert classifier.requests == []


def test_matcher_rejects_answers_without_scores():
    class Unscored:
        def classify(self, request: ClassificationRequest) -> ClassificationResult:
            return ClassificationResult(status="classified", answers={"master": ChoiceAnswer(choice="first")})

    with pytest.raises(InvalidInferenceResultError):
        MasterMatcher(translator, Unscored()).choose(REWORDED, {"first": ORIGINAL})


def test_model_joins_differently_worded_report_nearby(client: TestClient, signed_in, use_matcher):
    _, headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location, title=ORIGINAL)
    classifier = use_matcher(Classifier())

    second = create_report(client, headers, moved(location, north_m=15), title=REWORDED)

    assert second["master_report_id"] == first["master_report_id"]
    assert list(classifier.requests[0].questions["master"].criteria) == [first["master_report_id"], UNMATCHED]


@pytest.mark.parametrize("classifier", [Classifier(0.52, 0.48), Classifier(error=InferenceUnavailableError("down"))])
def test_report_creates_master_when_model_is_unsure_or_fails(client: TestClient, signed_in, use_matcher, classifier):
    _, headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location, title=ORIGINAL)
    use_matcher(classifier)

    second = create_report(client, headers, location, title=REWORDED)

    assert second["master_report_id"] != first["master_report_id"]
    assert len(classifier.requests) == 1


def test_model_answers_unmatched_for_other_problem(client: TestClient, signed_in, use_matcher):
    _, headers = signed_in("user")
    location = random_location()
    first = create_report(client, headers, location, title=ORIGINAL)
    classifier = use_matcher(Classifier())

    second = create_report(client, headers, location, title="Zepsuta latarnia")

    assert second["master_report_id"] != first["master_report_id"]
    assert len(classifier.requests) == 1


def test_model_is_skipped_without_candidates_or_with_similar_title(client: TestClient, signed_in, use_matcher):
    _, headers = signed_in("user")
    location = random_location()
    classifier = use_matcher(Classifier())

    first = create_report(client, headers, location, title="Dziura w jezdni")
    second = create_report(client, headers, location, title="Dziura w jezdni na Długiej")
    create_report(client, headers, moved(location, north_m=60), title=REWORDED)

    assert second["master_report_id"] == first["master_report_id"]
    assert classifier.requests == []


def test_suggestion_must_still_be_a_candidate(client: TestClient, signed_in, connection: psycopg.Connection):
    _, headers = signed_in("user")
    location = random_location()
    near = UUID(create_report(client, headers, location, title=ORIGINAL)["master_report_id"])
    far = UUID(create_report(client, headers, moved(location, north_m=100), title=ORIGINAL)["master_report_id"])
    category_id = reference_id(client, "/report-categories", "issue")

    def assign(suggestion: UUID) -> tuple[UUID, bool]:
        return matching.assign_master_for_publication(
            connection, category_id, REWORDED, REWORDED, Location.model_validate(location), suggestion
        )

    assert assign(near) == (near, False)
    for suggestion in (far, uuid4()):
        master_id, created = assign(suggestion)
        assert created and master_id not in (near, far, suggestion)
        # the empty master would match the next title.
        matching.delete_if_empty(connection, master_id)


def test_master_matching_fixture_is_consistent():
    cases = json.loads((Path(__file__).parents[3] / "tests/fixtures/master_matching.json").read_text())

    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["title"] and all(case["candidates"])
        assert case["expected"] is None or 0 <= case["expected"] < len(case["candidates"])
    assert {case["expected"] is None for case in cases} == {True, False}
