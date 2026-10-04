from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field

from app import gemini

app = FastAPI(title="eHackYeah2026 Gemini")


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prompt: str = Field(min_length=1, strict=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_class=Response)
def generate(payload: ImageRequest) -> Response:
    media_type, data = gemini.generate_image(payload.prompt)
    return Response(content=data, media_type=media_type)
