import base64
import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.genai import errors, types

import example
from app import gemini, storage
from app.main import app

KEY = "reports/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222.jpg"
PHOTO = b"\xff\xd8\xffreference"
DESIGNS = ["Wooden playground", "Colorful playground", "Nature playground"]


def response_with_parts(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=list(parts)))])


def plan_response(prompts: list[str] = DESIGNS) -> types.GenerateContentResponse:
    return response_with_parts(types.Part(text=json.dumps({"prompts": prompts})))


def image_response(media_type: str = "image/png", data: bytes = b"generated") -> types.GenerateContentResponse:
    return response_with_parts(types.Part(inline_data=types.Blob(mime_type=media_type, data=data)))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.models.generate_content.side_effect = [plan_response(), *[image_response() for _ in DESIGNS]]
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
    results = response.json()["variants"]
    assert len(results) == 3
    calls = client.models.generate_content.call_args_list
    assert [call.kwargs["model"] for call in calls] == [gemini.PROMPT_MODEL, *[gemini.IMAGE_MODEL] * 3]
    assert payload["description"] in calls[0].kwargs["contents"][0].text
    assert calls[0].kwargs["config"].system_instruction == gemini.PLANNING_INSTRUCTIONS
    for call in calls:
        references = [part.inline_data for part in call.kwargs["contents"][1:]]
        assert [(part.mime_type, part.data) for part in references] == [
            ("image/jpeg", PHOTO),
            ("image/png", second_photo),
        ]
    for number, result in enumerate(results):
        assert DESIGNS[number] in result["prompt"]
        assert gemini.VISUALIZATION_GUIDANCE in result["prompt"]
        assert result["prompt"] == calls[number + 1].kwargs["contents"][0].text
        assert result["media_type"] == "image/png"
        assert base64.b64decode(result["image_base64"]) == b"generated"


@pytest.mark.parametrize("media_type", ["image/png", "image/jpeg", "image/webp"])
def test_one_variant_and_image_after_text_and_thought(client: MagicMock, payload: dict, media_type: str):
    payload["variants"] = 1
    client.models.generate_content.side_effect = [
        plan_response(DESIGNS[:1]),
        response_with_parts(
            types.Part(text="Generated an image."),
            types.Part(thought=True, inline_data=types.Blob(mime_type="image/png", data=b"internal")),
            types.Part(inline_data=types.Blob(mime_type=media_type, data=b"generated")),
        ),
    ]
    response = TestClient(app).post("/generate", json=payload)
    assert response.status_code == 200
    assert len(response.json()["variants"]) == 1
    assert response.json()["variants"][0]["media_type"] == media_type
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
    client.models.generate_content.side_effect = [plan_response(), image_response(), response]
    result = TestClient(app).post("/generate", json=payload)
    assert result.status_code == 502
    assert result.json() == {"detail": "Gemini did not return an image"}
    assert client.models.generate_content.call_count == 3


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not JSON",
        "{}",
        '{"prompts": [""]}',
        '{"prompts": ["   "]}',
        '{"prompts": [3]}',
        '{"prompts": ["only one"]}',
        '{"prompts": ["same", "same", "same"]}',
        '{"prompts": ["one", "two", "three", "four"]}',
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
        {"report_type": "issue"},
        {"report_type": None},
        {"description": ""},
        {"description": "   "},
        {"description": 123},
        {"description": None},
        {"variants": 0},
        {"variants": 4},
        {"variants": True},
        {"variants": "3"},
        {"variants": 1.5},
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


def test_example_saves_variants_and_prompts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
):
    monkeypatch.setattr(example, "__file__", str(tmp_path / "example.py"))
    mock = MagicMock(return_value=[(design, "image/jpeg", b"generated") for design in DESIGNS])
    monkeypatch.setattr(example, "generate_visualizations", mock)
    example.main()
    mock.assert_called_once_with(example.DESCRIPTION, [("image/jpeg", example.PHOTO.read_bytes())], 3)
    paths = [tmp_path / "output" / f"variant-{number}.jpg" for number in range(1, 4)]
    assert [path.read_bytes() for path in paths] == [b"generated"] * 3
    assert capsys.readouterr().out.splitlines() == [str(path) for path in paths]
    prompts = json.loads((tmp_path / "output" / "prompts.json").read_text())
    assert [proposal["prompt"] for proposal in prompts] == DESIGNS


def test_core_requires_description_photos_and_valid_count(client: MagicMock):
    with pytest.raises(HTTPException) as error:
        gemini.generate_visualizations("A playground", [], 3)
    assert error.value.status_code == 422
    client.models.generate_content.assert_not_called()
