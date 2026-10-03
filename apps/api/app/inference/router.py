from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from app import storage
from app.auth import CurrentUser
from app.inference.contracts import ImageInput, InferenceUnavailableError, InvalidInferenceResultError
from app.inference.service import Inference, InferenceRequest, InferenceResult

router = APIRouter(prefix="/inference", tags=["inference"])


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
    photo = None
    if image is not None:
        data = image.file.read(storage.MAX_PHOTO_BYTES + 1)
        if len(data) > storage.MAX_PHOTO_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Photo exceeds the upload size limit")
        extension = storage.detect_extension(data)
        if extension is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Photos must be JPEG, PNG, or WebP images")
        photo = ImageInput(data=data, media_type=storage.MEDIA_TYPES[extension])
    try:
        return inference.analyze(body, photo)
    except InferenceUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Inference provider is unavailable") from None
    except InvalidInferenceResultError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Inference provider returned an invalid result") from None
