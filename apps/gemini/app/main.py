import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import gemini, storage


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    gemini.log_credentials_status()
    yield


app = FastAPI(title="eHackYeah2026 Gemini", lifespan=lifespan)


class Photo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_key: str = Field(
        pattern=r"^(?:reports/[0-9a-f-]{36}/[0-9a-f-]{36}(?:_generated(?:_[0-9a-f-]{36})?)?"
        r"|visualizations/[0-9a-f-]{36}/(?:[0-9a-f-]{36}|result))\.(jpg|png|webp)$"
    )


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    report_type: gemini.ReportType
    description: str = Field(min_length=1, strict=True)
    photos: list[Photo] = Field(min_length=1, max_length=5)


class Visualization(BaseModel):
    prompt: str
    media_type: str
    image_base64: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_model=Visualization)
def generate(payload: ImageRequest) -> Visualization:
    photos = [storage.read_photo(photo.storage_key) for photo in payload.photos]
    if sum(len(data) for _, data in photos) > storage.MAX_TOTAL_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photos can have at most 20 MB in total")
    prompt, media_type, data = gemini.generate_visualization(payload.report_type, payload.description, photos)
    return Visualization(prompt=prompt, media_type=media_type, image_base64=base64.b64encode(data).decode("ascii"))
