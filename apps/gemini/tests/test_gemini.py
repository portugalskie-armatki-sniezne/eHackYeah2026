from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.genai import errors, types

import example
from app.gemini import generate_image
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    monkeypatch.setattr("app.gemini.genai.Client", factory)
    return client


def response_with_parts(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=list(parts)))])


def test_returns_image_after_text_and_thought(client: MagicMock):
    client.models.generate_content.return_value = response_with_parts(
        types.Part(text="Generated an image."),
        types.Part(thought=True, inline_data=types.Blob(mime_type="image/png", data=b"internal")),
        types.Part(inline_data=types.Blob(mime_type="image/png", data=b"generated")),
    )

    assert generate_image("Park with benches") == ("image/png", b"generated")


@pytest.mark.parametrize(
    "response",
    [
        types.GenerateContentResponse(),
        types.GenerateContentResponse(
            prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY")
        ),
        response_with_parts(types.Part(text="Cannot generate this image.")),
        response_with_parts(types.Part(inline_data=types.Blob(mime_type="image/png", data=b""))),
        response_with_parts(types.Part(inline_data=types.Blob(mime_type="text/plain", data=b"text"))),
    ],
)
def test_missing_image(client: MagicMock, response: types.GenerateContentResponse):
    client.models.generate_content.return_value = response

    with pytest.raises(HTTPException) as error:
        generate_image("Park")

    assert error.value.status_code == 502
    assert error.value.detail == "Gemini did not return an image"


@pytest.mark.parametrize(
    ("exception", "status", "detail"),
    [
        (errors.ClientError(401, {"error": {"message": "private response"}}), 502, "Gemini image generation failed"),
        (errors.ClientError(429, {"error": {"message": "private response"}}), 503, "Gemini quota exceeded"),
        (errors.ClientError(403, {"error": {"message": "private response"}}), 502, "Gemini image generation failed"),
        (errors.ServerError(500, {"error": {"message": "private response"}}), 502, "Gemini image generation failed"),
        (httpx.ConnectError("private response"), 502, "Gemini connection failed"),
        (httpx.ReadTimeout("private response"), 502, "Gemini connection failed"),
        (DefaultCredentialsError("private response"), 503, "Google Cloud credentials are missing or invalid"),
        (RefreshError("private response"), 503, "Google Cloud credentials are missing or invalid"),
    ],
)
def test_upstream_error_does_not_expose_response(client: MagicMock, exception: Exception, status: int, detail: str):
    client.models.generate_content.side_effect = exception

    with pytest.raises(HTTPException) as error:
        generate_image("Park")

    assert error.value.status_code == status
    assert error.value.detail == detail


@pytest.mark.parametrize("media_type", ["image/png", "image/jpeg", "image/webp"])
def test_endpoint_returns_image(client: MagicMock, media_type: str):
    client.models.generate_content.return_value = response_with_parts(
        types.Part(inline_data=types.Blob(mime_type=media_type, data=b"generated"))
    )

    response = TestClient(app).post("/generate", json={"prompt": "Park"})

    assert response.status_code == 200
    assert response.headers["content-type"] == media_type
    assert response.content == b"generated"


@pytest.mark.parametrize("prompt", ["", "   ", 123, None])
def test_invalid_prompt_does_not_call_gemini(client: MagicMock, prompt: object):
    response = TestClient(app).post("/generate", json={"prompt": prompt})

    assert response.status_code == 422
    client.models.generate_content.assert_not_called()


def test_missing_project(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "unrelated-key")

    response = TestClient(app).post("/generate", json={"prompt": "Park"})

    assert response.status_code == 503
    assert response.json() == {"detail": "GOOGLE_CLOUD_PROJECT is not configured"}


def test_health_without_project(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_credential_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
    monkeypatch.setenv("GEMINI_API_KEY", "unrelated-key")

    response = TestClient(app).post("/generate", json={"prompt": "Park"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Google Cloud credentials are missing or invalid"}


def test_example_saves_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture):
    monkeypatch.setattr(example, "__file__", str(tmp_path / "example.py"))
    monkeypatch.setattr(example, "generate_image", lambda prompt: ("image/jpeg", b"generated"))

    example.main()

    path = tmp_path / "output" / "example.jpg"
    assert path.read_bytes() == b"generated"
    assert capsys.readouterr().out.strip() == str(path)
