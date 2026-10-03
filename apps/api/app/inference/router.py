from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from app import storage
from app.auth import CurrentUser
from app.inference.contracts import (
    ImageInput,
    InferenceUnavailableError,
)
from app.inference.entities import (
    EntityClassificationRequest,
    EntityClassificationResult,
    EntityClassificationService,
    load_entity_question,
)
from app.inference.service import Inference, InferenceRequest, InferenceResult

router = APIRouter(prefix="/inference", tags=["inference"])


def read_image(image: UploadFile | None) -> ImageInput | None:
    if image is None:
        return None
    data = image.file.read(storage.MAX_PHOTO_BYTES + 1)
    if len(data) > storage.MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Photo exceeds the upload size limit")
    extension = storage.detect_extension(data)
    if extension is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Photos must be JPEG, PNG, or WebP images")
    return ImageInput(data=data, media_type=storage.MEDIA_TYPES[extension])


@router.post("", description="Translate text and classify it with supplied questions and an optional photo.")
def analyze(
    payload: Annotated[str, Form(description="JSON containing text, source_language, target_language, and questions")],
    _: CurrentUser,
    inference: Inference,
    image: Annotated[UploadFile | None, File(description="Optional JPEG, PNG, or WebP photo")] = None,
) -> InferenceResult:
    try:
        body = InferenceRequest.model_validate_json(payload)
    except ValidationError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.errors(include_context=False, include_url=False)
        ) from None
    return inference.analyze(body, read_image(image))


@router.post("/service-entity", description="Choose exactly one service entity type from a report and optional photo.")
def classify_service_entity(
    payload: Annotated[str, Form(description="JSON containing title, description, and source_language (pl or en)")],
    _: CurrentUser,
    inference: Inference,
    image: Annotated[UploadFile | None, File(description="Optional JPEG, PNG, or WebP photo")] = None,
) -> EntityClassificationResult:
    try:
        body = EntityClassificationRequest.model_validate_json(payload)
    except ValidationError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.errors(include_context=False, include_url=False)
        ) from None
    try:
        question = load_entity_question()
    except (OSError, ValueError) as error:
        raise InferenceUnavailableError("Invalid service entity criteria configuration") from error
    return EntityClassificationService(inference, question).classify(body, read_image(image))
