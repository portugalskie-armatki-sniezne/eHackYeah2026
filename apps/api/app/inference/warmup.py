from app.inference.contracts import InferenceUnavailableError
from app.inference.entities import EntityClassificationRequest, EntityClassificationService, load_entity_question
from app.inference.runtime import configured_classifier, configured_translator
from app.inference.service import InferenceService


def warmup() -> None:
    service = EntityClassificationService(
        InferenceService(configured_translator(), configured_classifier()), load_entity_question()
    )
    result = service.classify(
        EntityClassificationRequest(title="Dziura w jezdni", description="Na drodze jest głęboka dziura.")
    )
    if result.translation.status != "translated":
        raise InferenceUnavailableError("Startup requires working translation and classification models")


if __name__ == "__main__":
    warmup()
