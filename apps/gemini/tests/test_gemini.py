import base64
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.genai import errors, types

import example
from app import gemini, storage
from app.main import app

KEY = "reports/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222.jpg"
PHOTO = b"\xff\xd8\xffreference"
DESIGN = "Wooden playground"


def response_with_parts(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=list(parts)))])


def plan_response(prompt: str = DESIGN) -> types.GenerateContentResponse:
    return response_with_parts(types.Part(text=json.dumps({"prompt": prompt})))


def image_response(media_type: str = "image/png", data: bytes = b"generated") -> types.GenerateContentResponse:
    return response_with_parts(types.Part(inline_data=types.Blob(mime_type=media_type, data=data)))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.models.generate_content.side_effect = [plan_response(), image_response()]
    monkeypatch.setattr("app.gemini.genai.Client", factory)
    return client


@pytest.fixture
def payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    path = tmp_path / KEY
    path.parent.mkdir(parents=True)
    path.write_bytes(PHOTO)
    return {"report_type": "improvement", "description": "A playground with a slide", "photos": [{"storage_key": KEY}]}


def test_endpoint_runs_both_stages_with_all_reference_photos(client: MagicMock, payload: dict, tmp_path: Path):
    second_key = KEY.replace("22222222-2222-4222-8222-222222222222.jpg", "33333333-3333-4333-8333-333333333333.png")
    second_photo = b"\x89PNG\r\n\x1a\nsecond view"
    (tmp_path / second_key).write_bytes(second_photo)
    payload["photos"].append({"storage_key": second_key})

    response = TestClient(app).post("/generate", json=payload)

    assert response.status_code == 200
    assert gemini.genai.Client.call_args.kwargs["http_options"].retry_options.attempts == 1
    calls = client.models.generate_content.call_args_list
    assert [call.kwargs["model"] for call in calls] == [gemini.PROMPT_MODEL, gemini.IMAGE_MODEL]
    assert payload["description"] in calls[0].kwargs["contents"][0].text
    assert calls[0].kwargs["config"].system_instruction == gemini.planning_instructions("improvement")
    for call in calls:
        references = [part.inline_data for part in call.kwargs["contents"][1:]]
        assert [(part.mime_type, part.data) for part in references] == [
            ("image/jpeg", PHOTO),
            ("image/png", second_photo),
        ]
    result = response.json()
    assert DESIGN in result["prompt"]
    assert gemini.VISUALIZATION_GUIDANCE["improvement"] in result["prompt"]
    assert result["prompt"] == calls[1].kwargs["contents"][0].text
    assert result["media_type"] == "image/png"
    assert base64.b64decode(result["image_base64"]) == b"generated"


def test_issue_report_is_drawn_repaired(client: MagicMock, payload: dict):
    payload["report_type"] = "issue"
    payload["description"] = "A broken bench with missing slats"

    response = TestClient(app).post("/generate", json=payload)

    assert response.status_code == 200
    calls = client.models.generate_content.call_args_list
    assert "Reported fault: " + payload["description"] in calls[0].kwargs["contents"][0].text
    assert calls[0].kwargs["config"].system_instruction == gemini.planning_instructions("issue")
    assert "repaired" in gemini.planning_instructions("issue")
    assert response.json()["prompt"].startswith(gemini.VISUALIZATION_GUIDANCE["issue"])


@pytest.mark.parametrize("suffix", ["_generated", "_generated_7e8d9c0b-1a2f-4b3c-8d9e-0f1a2b3c4d5e"])
def test_generated_reference_photo(client: MagicMock, payload: dict, tmp_path: Path, suffix: str):
    key = KEY.removesuffix(".jpg") + suffix + ".jpg"
    (tmp_path / KEY).rename(tmp_path / key)
    payload["photos"] = [{"storage_key": key}]

    response = TestClient(app).post("/generate", json=payload)

    assert response.status_code == 200
    for call in client.models.generate_content.call_args_list:
        assert call.kwargs["contents"][1].inline_data.data == PHOTO


@pytest.mark.parametrize("name", ["22222222-2222-4222-8222-222222222222", "result"])
def test_visualization_job_photo(client: MagicMock, payload: dict, tmp_path: Path, name: str):
    key = f"visualizations/11111111-1111-4111-8111-111111111111/{name}.jpg"
    path = tmp_path / key
    path.parent.mkdir(parents=True)
    path.write_bytes(PHOTO)
    payload["photos"] = [{"storage_key": key}]
    assert TestClient(app).post("/generate", json=payload).status_code == 200


@pytest.mark.parametrize("media_type", ["image/png", "image/jpeg", "image/webp"])
def test_single_image_and_image_after_text_and_thought(client: MagicMock, payload: dict, media_type: str):
    client.models.generate_content.side_effect = [
        plan_response(),
        response_with_parts(
            types.Part(text="Generated an image."),
            types.Part(thought=True, inline_data=types.Blob(mime_type="image/png", data=b"internal")),
            types.Part(inline_data=types.Blob(mime_type=media_type, data=b"generated")),
        ),
    ]
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == 200
    assert response.json()["media_type"] == media_type
    assert client.models.generate_content.call_count == 2


@pytest.mark.parametrize(
    "response",
    [
        types.GenerateContentResponse(),
        types.GenerateContentResponse(
            prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY")
        ),
        response_with_parts(types.Part(text="Cannot generate this image.")),
        image_response(data=b""),
        image_response(media_type="text/plain"),
    ],
)
def test_missing_image_returns_no_partial_result(
    client: MagicMock, payload: dict, response: types.GenerateContentResponse
):
    client.models.generate_content.side_effect = [plan_response(), response]
    result = TestClient(app).post("/generate", json=payload)
    assert result.status_code == 502
    assert result.json() == {"detail": "Gemini did not return an image"}
    assert client.models.generate_content.call_count == 2


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not JSON",
        "{}",
        '{"prompt": ""}',
        '{"prompt": "   "}',
        '{"prompt": 3}',
        '{"prompts": ["unexpected"]}',
    ],
)
def test_invalid_plan_does_not_generate_images(client: MagicMock, payload: dict, text: str):
    client.models.generate_content.side_effect = [response_with_parts(types.Part(text=text))]
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == 502
    client.models.generate_content.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "status", "detail"),
    [
        (
            errors.ClientError(401, {"error": {"message": "private response"}}),
            502,
            "Gemini visualization generation failed",
        ),
        (errors.ClientError(429, {"error": {"message": "private response"}}), 503, "Gemini quota exceeded"),
        (
            errors.ClientError(403, {"error": {"message": "private response"}}),
            502,
            "Gemini visualization generation failed",
        ),
        (
            errors.ServerError(500, {"error": {"message": "private response"}}),
            502,
            "Gemini visualization generation failed",
        ),
        (httpx.ConnectError("private response"), 502, "Gemini connection failed"),
        (httpx.ReadTimeout("private response"), 502, "Gemini connection failed"),
        (DefaultCredentialsError("private response"), 503, "Google Cloud credentials are missing or invalid"),
        (RefreshError("private response"), 503, "Google Cloud credentials are missing or invalid"),
    ],
)
@pytest.mark.parametrize("image_stage", [False, True])
def test_errors_in_either_stage_are_sanitized(
    client: MagicMock, payload: dict, exception: Exception, status: int, detail: str, image_stage: bool
):
    client.models.generate_content.side_effect = [plan_response(), exception] if image_stage else [exception]
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == status
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "changes",
    [
        {"report_type": "complaint"},
        {"report_type": None},
        {"description": ""},
        {"description": "   "},
        {"description": 123},
        {"description": None},
        {"variants": 3},
        {"photos": []},
        {"photos": [{"storage_key": KEY}] * 6},
        {"photos": [{"storage_key": "../../project-key.json"}]},
        {"photos": [{"storage_key": "/etc/passwd"}]},
        {"photos": [{"storage_key": KEY, "extra": "value"}]},
        {"prompt": "raw prompt"},
    ],
)
def test_invalid_request_does_not_call_gemini(client: MagicMock, payload: dict, changes: dict):
    payload.update(changes)
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == 422
    client.models.generate_content.assert_not_called()


@pytest.mark.parametrize("field", ["report_type", "description", "photos"])
def test_required_fields(client: MagicMock, payload: dict, field: str):
    del payload[field]
    assert TestClient(app).post("/generate", json=payload).status_code == 422
    client.models.generate_content.assert_not_called()


@pytest.mark.parametrize(("data", "status"), [(None, 404), (b"invalid", 422), (b"x" * 11, 413)])
def test_invalid_photo_does_not_call_gemini(
    client: MagicMock, payload: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: bytes | None, status: int
):
    path = tmp_path / KEY
    if data is None:
        path.unlink()
    else:
        path.write_bytes(data)
    monkeypatch.setattr(storage, "MAX_PHOTO_BYTES", 10)
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == status
    client.models.generate_content.assert_not_called()


def test_total_photo_limit(client: MagicMock, payload: dict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage, "MAX_TOTAL_PHOTO_BYTES", len(PHOTO) - 1)
    assert TestClient(app).post("/generate", json=payload).status_code == 413
    client.models.generate_content.assert_not_called()


def test_symlink_outside_upload_dir_is_rejected(
    client: MagicMock, payload: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "uploads"
    path = root / KEY
    path.parent.mkdir(parents=True)
    path.symlink_to(tmp_path / KEY)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    assert TestClient(app).post("/generate", json=payload).status_code == 422
    client.models.generate_content.assert_not_called()


def test_photo_read_failure_is_sanitized(client: MagicMock, payload: dict, monkeypatch: pytest.MonkeyPatch):
    def fail(*args, **kwargs):
        raise PermissionError("private path")

    monkeypatch.setattr(Path, "open", fail)
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == 503
    assert response.json() == {"detail": "Photo cannot be read"}
    client.models.generate_content.assert_not_called()


def test_default_photo_dir_is_shared_with_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    assert storage.upload_dir() == Path(storage.__file__).resolve().parents[2] / "api" / "uploads"


def test_missing_project(monkeypatch: pytest.MonkeyPatch, payload: dict):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "unrelated-key")
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == 503
    assert response.json() == {"detail": "GOOGLE_CLOUD_PROJECT is not configured"}


def test_health_without_project(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_credential_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload: dict):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
    monkeypatch.setenv("GEMINI_API_KEY", "unrelated-key")
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == 503
    assert response.json() == {"detail": "Google Cloud credentials are missing or invalid"}


def test_example_saves_image_and_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture):
    monkeypatch.setattr(example, "__file__", str(tmp_path / "example.py"))
    mock = MagicMock(return_value=(DESIGN, "image/jpeg", b"generated"))
    monkeypatch.setattr(example, "generate_visualization", mock)
    example.main()
    mock.assert_called_once_with("improvement", example.DESCRIPTION, [("image/jpeg", example.PHOTO.read_bytes())])
    path = tmp_path / "output" / "visualization.jpg"
    assert path.read_bytes() == b"generated"
    assert (tmp_path / "output" / "prompt.txt").read_text() == DESIGN + "\n"
    assert capsys.readouterr().out.strip() == str(path)


def test_core_requires_description_photos_and_valid_count(client: MagicMock):
    with pytest.raises(HTTPException) as error:
        gemini.generate_visualization("improvement", "A playground", [])
    assert error.value.status_code == 422
    with pytest.raises(HTTPException) as error:
        gemini.generate_visualization("complaint", "A playground", [("image/jpeg", PHOTO)])
    assert error.value.status_code == 422
    client.models.generate_content.assert_not_called()


def service_account_key(path: Path) -> Path:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "key-project",
                "private_key_id": "test",
                "private_key": private_key.decode(),
                "client_email": "visualizer@key-project.iam.gserviceaccount.com",
                "client_id": "1",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    return path


def test_startup_logs_loaded_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(service_account_key(tmp_path / "key.json")))
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

    with caplog.at_level(logging.INFO, logger="uvicorn.error"), TestClient(app):
        pass

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    assert "loaded" in record.getMessage()
    assert "visualizer@key-project.iam.gserviceaccount.com" in record.getMessage()
    assert "key project key-project, GOOGLE_CLOUD_PROJECT test-project" in record.getMessage()
    assert "PRIVATE KEY" not in caplog.text


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (None, "does not exist"),
        ("directory", "is a directory, the key file is missing on the host"),
        ("not json", "is not a valid service-account key (JSONDecodeError)"),
        ('{"type": "service_account", "private_key": "secret-material"}', "is not a valid service-account key"),
    ],
)
def test_startup_logs_unusable_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, content: str | None, reason: str
):
    path = tmp_path / "key.json"
    if content == "directory":
        path.mkdir()
    elif content is not None:
        path.write_text(content)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        gemini.log_credentials_status()

    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert f"{path} {reason}" in record.getMessage()
    assert "secret-material" not in caplog.text


def test_startup_logs_default_credentials_without_key_file(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        gemini.log_credentials_status()

    assert caplog.records[-1].levelno == logging.INFO
    assert "Application Default Credentials" in caplog.text
