import base64
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import gemini, storage

app = FastAPI(title="eHackYeah2026 Gemini")


class Photo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_key: str = Field(pattern=r"^reports/[0-9a-f-]{36}/[0-9a-f-]{36}\.(jpg|png|webp)$")


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    report_type: Literal["improvement"]
    description: str = Field(min_length=1, strict=True)
    photos: list[Photo] = Field(min_length=1, max_length=5)
    variants: int = Field(default=3, ge=1, le=3, strict=True)


class Visualization(BaseModel):
    prompt: str
    media_type: str
    image_base64: str


class ImageResponse(BaseModel):
    variants: list[Visualization]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_model=ImageResponse)
def generate(payload: ImageRequest) -> ImageResponse:
    photos = [storage.read_photo(photo.storage_key) for photo in payload.photos]
    if sum(len(data) for _, data in photos) > storage.MAX_TOTAL_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photos can have at most 20 MB in total")
    images = gemini.generate_visualizations(payload.description, photos, payload.variants)
    return ImageResponse(
        variants=[
            Visualization(prompt=prompt, media_type=media_type, image_base64=base64.b64encode(data).decode("ascii"))
            for prompt, media_type, data in images
        ]
    )
