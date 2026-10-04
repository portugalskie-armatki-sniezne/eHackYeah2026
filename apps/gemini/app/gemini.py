import os

import httpx
from fastapi import HTTPException
from google import genai
from google.auth.exceptions import GoogleAuthError
from google.genai import errors, types

MODEL = "gemini-3.1-flash-image"
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def generate_image(prompt: str) -> tuple[str, bytes]:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project:
        raise HTTPException(status_code=503, detail="GOOGLE_CLOUD_PROJECT is not configured")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"

    try:
        with genai.Client(
            enterprise=True,
            project=project,
            location=location,
            http_options=types.HttpOptions(api_version="v1", timeout=120_000),
        ) as client:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
    except errors.APIError as error:
        if error.code == 429:
            raise HTTPException(status_code=503, detail="Gemini quota exceeded") from error
        raise HTTPException(status_code=502, detail="Gemini image generation failed") from error
    except GoogleAuthError as error:
        raise HTTPException(status_code=503, detail="Google Cloud credentials are missing or invalid") from error
    except (httpx.HTTPError, OSError) as error:
        raise HTTPException(status_code=502, detail="Gemini connection failed") from error

    for part in response.parts or []:
        image = part.inline_data
        if not part.thought and image and image.data and image.mime_type in IMAGE_TYPES:
            return image.mime_type, image.data
    raise HTTPException(status_code=502, detail="Gemini did not return an image")
