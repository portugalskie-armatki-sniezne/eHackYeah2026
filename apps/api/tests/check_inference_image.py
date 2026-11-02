from io import BytesIO

from PIL import Image

from app.inference.contracts import ImageInput
from app.inference.entities import EntityClassificationRequest, EntityClassificationService, load_entity_question
from app.inference.models import CHECKPOINTS
from app.inference.service import InferenceService, get_classifier, get_translator


def main() -> None:
    for checkpoint in CHECKPOINTS:
        if not checkpoint.downloaded():
            raise RuntimeError(f"Missing checkpoint: {checkpoint.repository}")

    service = EntityClassificationService(InferenceService(get_translator(), get_classifier()), load_entity_question())
    request = EntityClassificationRequest(
        title="Dziura w jezdni", description="Głęboka dziura w drodze wymaga naprawy."
    )
    photo = BytesIO()
    Image.new("RGB", (64, 64), color="gray").save(photo, format="PNG")
    for image in (None, ImageInput(data=photo.getvalue(), media_type="image/png")):
        result = service.classify(request, image)
        if result.translation.status != "translated" or not result.scores:
            raise RuntimeError("Expected translation and classification from the bundled models")
        print(f"Inference ready ({'image' if image else 'text'}): {result.entity_type}")


if __name__ == "__main__":
    main()
