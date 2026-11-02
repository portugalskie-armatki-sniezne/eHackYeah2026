import smtplib
import ssl
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app

PAYLOAD = {
    "to": "recipient@example.com",
    "subject": "Aktualizacja zgłoszenia",
    "description": "Na ścieżce przy parku brakuje oświetlenia.",
    "report_type": "issue",
    "first_name": "Jan",
    "last_name": "Kowalski",
}


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-app-password")
    monkeypatch.setenv("SMTP_MOCK", "true")
    monkeypatch.setenv("SMTP_MOCK_DESTINATION", "demo@example.com")
    smtp = MagicMock()
    monkeypatch.setattr("app.main.smtplib.SMTP", smtp)
    return smtp


@pytest.mark.parametrize(
    ("report_type", "intro", "other_intro"),
    [
        ("issue", "zgłoszenie problemu", "propozycję usprawnienia"),
        ("improvement", "propozycję usprawnienia", "zgłoszenie problemu"),
    ],
)
def test_send_plaintext(smtp: MagicMock, report_type: str, intro: str, other_intro: str):
    response = TestClient(app).post("/send", json=PAYLOAD | {"report_type": report_type})

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
    connection = smtp.return_value.__enter__.return_value
    context = connection.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    connection.login.assert_called_once_with("sender@gmail.com", "test-app-password")
    message = connection.send_message.call_args.args[0]
    assert message["From"] == "sender@gmail.com"
    assert message["To"] == "demo@example.com"
    assert message["Subject"] == PAYLOAD["subject"]
    assert message.get_content_type() == "multipart/alternative"
    assert message.get_body(("plain",)).get_content_type() == "text/plain"
    assert message.get_body(("html",)).get_content_type() == "text/html"
    content = message.get_body(("plain",)).get_content()
    assert content.count(PAYLOAD["description"]) == 1
    assert intro in content
    assert other_intro not in content
    assert content.startswith("Szanowni Państwo,")
    assert "Zgłoszone przez: Jan Kowalski" in content
    assert content.rstrip().endswith("Zespół pomożeMy")
    html = message.get_body(("html",)).get_content()
    assert "<strong>Zgłoszone przez:</strong> Jan Kowalski" in html
    assert html.count("<strong>pomożeMy</strong>") == 1
    assert (
        "<strong>Opis zgłoszenia:</strong>" in html
        if report_type == "issue"
        else "<strong>Opis propozycji:</strong>" in html
    )
    assert "<strong>Zespół pomożeMy</strong>" not in html
    assert connection.send_message.call_args.kwargs["to_addrs"] == ["demo@example.com"]


@pytest.mark.parametrize("flag", ["true", "TRUE", " true "])
def test_mock_redirects_mail(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, flag: str):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SMTP_MOCK", flag)
    monkeypatch.setenv("SMTP_MOCK_DESTINATION", "team@example.com")

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 200
    connection = smtp.return_value.__enter__.return_value
    message = connection.send_message.call_args.args[0]
    assert message["To"] == "team@example.com"
    assert connection.send_message.call_args.kwargs["to_addrs"] == ["team@example.com"]
    assert message["Subject"] == PAYLOAD["subject"]
    assert message.get_body(("plain",)).get_content().count(PAYLOAD["description"]) == 1


@pytest.mark.parametrize("flag", ["false", None])
def test_disabled_mock_blocks_sending(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, flag: str | None):
    if flag is None:
        monkeypatch.delenv("SMTP_MOCK")
    else:
        monkeypatch.setenv("SMTP_MOCK", flag)
    monkeypatch.setenv("SMTP_MOCK_DESTINATION", "team@example.com")

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 503
    smtp.assert_not_called()


@pytest.mark.parametrize("destination", [None, "", "invalid", "team@example.com, other@example.com"])
def test_mock_requires_valid_destination(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, destination: str | None):
    monkeypatch.setenv("SMTP_MOCK", "true")
    if destination is not None:
        monkeypatch.setenv("SMTP_MOCK_DESTINATION", destination)
    else:
        monkeypatch.delenv("SMTP_MOCK_DESTINATION")

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 503
    smtp.assert_not_called()


@pytest.mark.parametrize("flag", ["", "tru", "yes"])
def test_invalid_mock_flag_blocks_sending(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, flag: str):
    monkeypatch.setenv("SMTP_MOCK", flag)

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 503
    smtp.assert_not_called()


@pytest.mark.parametrize("variable", ["SMTP_USER", "SMTP_PASSWORD"])
def test_missing_credentials(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, variable: str):
    monkeypatch.delenv(variable)

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 503
    smtp.assert_not_called()


@pytest.mark.parametrize(
    ("stage", "error"),
    [
        ("connect", TimeoutError("private connection details")),
        ("starttls", smtplib.SMTPNotSupportedError("private TLS details")),
        ("login", smtplib.SMTPAuthenticationError(535, b"private authentication details")),
        ("send_message", smtplib.SMTPDataError(554, b"private delivery details")),
    ],
)
def test_smtp_failure(smtp: MagicMock, stage: str, error: Exception):
    if stage == "connect":
        smtp.side_effect = error
    else:
        connection = smtp.return_value.__enter__.return_value
        getattr(connection, stage).side_effect = error

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 502
    assert response.json() == {"detail": "SMTP delivery failed"}


@pytest.mark.parametrize(
    "values",
    [
        {"to": "invalid"},
        {"subject": ""},
        {"subject": "Update\nBcc: other@example.com"},
        {"subject": "Update\rBcc: other@example.com"},
        {"subject": "Update\n"},
        {"description": ""},
        {"report_type": "initiative"},
        {"report_type": "../issue"},
        {"report_type": "issue.txt"},
        {"text": "Update"},
        {"html": "<p>Update</p>"},
    ],
)
def test_invalid_mail(smtp: MagicMock, values: dict[str, str]):
    response = TestClient(app).post("/send", json=PAYLOAD | values)

    assert response.status_code == 422
    smtp.assert_not_called()


@pytest.mark.parametrize("field", ["to", "subject", "description", "report_type"])
def test_missing_required_field(smtp: MagicMock, field: str):
    payload = PAYLOAD.copy()
    del payload[field]

    response = TestClient(app).post("/send", json=payload)

    assert response.status_code == 422
    smtp.assert_not_called()


@pytest.mark.parametrize("report_type", ["issue", "improvement"])
def test_description_is_inserted_literally(smtp: MagicMock, report_type: str):
    description = "Opis: {description}, {unknown}, <b>oświetlenie</b>.\nDruga linia: zażółć gęślą jaźń."

    response = TestClient(app).post("/send", json=PAYLOAD | {"description": description, "report_type": report_type})

    assert response.status_code == 200
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert message.get_body(("plain",)).get_content_type() == "text/plain"
    assert message.get_body(("plain",)).get_content().count(description) == 1
    html = message.get_body(("html",)).get_content()
    assert "&lt;b&gt;oświetlenie&lt;/b&gt;" in html
    assert "<b>oświetlenie</b>" not in html
    assert "<br>\nDruga linia" in html


def test_templates_do_not_depend_on_working_directory(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 200
    smtp.return_value.__enter__.return_value.send_message.assert_called_once()


@pytest.mark.parametrize("report_type", ["issue", "improvement"])
@pytest.mark.parametrize("include_names", [False, True])
def test_anonymous_mail_hides_reporter(smtp: MagicMock, report_type: str, include_names: bool):
    payload = PAYLOAD | {"anonymous": True, "report_type": report_type}
    if not include_names:
        del payload["first_name"]
        del payload["last_name"]

    response = TestClient(app).post("/send", json=payload)

    assert response.status_code == 200
    content = smtp.return_value.__enter__.return_value.send_message.call_args.args[0].get_body(("plain",)).get_content()
    assert "Zgłoszone przez: anonimowo" in content
    assert "Jan" not in content
    assert "Kowalski" not in content
    assert content.count(PAYLOAD["description"]) == 1
    html = smtp.return_value.__enter__.return_value.send_message.call_args.args[0].get_body(("html",)).get_content()
    assert "<strong>Zgłoszone przez:</strong> anonimowo" in html
    assert "Jan" not in html
    assert "Kowalski" not in html


@pytest.mark.parametrize("anonymous", [False, None])
@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_named_mail_requires_both_names(smtp: MagicMock, anonymous: bool | None, field: str):
    payload = PAYLOAD.copy()
    del payload[field]
    if anonymous is not None:
        payload["anonymous"] = anonymous

    response = TestClient(app).post("/send", json=payload)

    assert response.status_code == 422
    smtp.assert_not_called()


@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize("value", [None, "", "   ", "Jan\nKowalski", "Jan\rKowalski"])
def test_named_mail_rejects_invalid_names(smtp: MagicMock, field: str, value: str | None):
    response = TestClient(app).post("/send", json=PAYLOAD | {field: value})

    assert response.status_code == 422
    smtp.assert_not_called()


@pytest.mark.parametrize("anonymous", ["false", "true", 0, 1, None])
def test_anonymous_requires_json_boolean(smtp: MagicMock, anonymous):
    response = TestClient(app).post("/send", json=PAYLOAD | {"anonymous": anonymous})

    assert response.status_code == 422
    smtp.assert_not_called()


def test_reporter_names_are_trimmed_and_inserted_literally(smtp: MagicMock):
    response = TestClient(app).post(
        "/send", json=PAYLOAD | {"first_name": "  Łukasz  ", "last_name": "  Żółć-{description}  "}
    )

    assert response.status_code == 200
    content = smtp.return_value.__enter__.return_value.send_message.call_args.args[0].get_body(("plain",)).get_content()
    assert "Zgłoszone przez: Łukasz Żółć-{description}\n" in content
    assert content.count(PAYLOAD["description"]) == 1


def test_health_without_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("report_type", ["issue", "improvement"])
@pytest.mark.parametrize("location", [{"longitude": 19.9449, "latitude": 50.0647}, {"longitude": 0, "latitude": 0}])
def test_location_links_to_correct_coordinates(smtp: MagicMock, report_type: str, location: dict[str, float]):
    response = TestClient(app).post("/send", json=PAYLOAD | {"report_type": report_type, "location": location})

    assert response.status_code == 200
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    content = message.get_body(("plain",)).get_content()
    link = content.split("Przybliżona lokalizacja zgłoszenia: ", 1)[1].splitlines()[0]
    url = urlparse(link)
    assert url.scheme == "https"
    assert url.netloc == "www.google.com"
    assert url.path == "/maps/search/"
    query = parse_qs(url.query)
    assert query["api"] == ["1"]
    assert [float(value) for value in query["query"][0].split(",")] == [location["latitude"], location["longitude"]]
    assert content.index(PAYLOAD["description"]) < content.index("Przybliżona lokalizacja")
    assert f'<a href="{link.replace("&", "&amp;")}">' in message.get_body(("html",)).get_content()


@pytest.mark.parametrize("report_type", ["issue", "improvement"])
@pytest.mark.parametrize("include_location", [False, True])
def test_missing_location_is_unspecified(smtp: MagicMock, report_type: str, include_location: bool):
    payload = PAYLOAD | {"report_type": report_type}
    if include_location:
        payload["location"] = None

    response = TestClient(app).post("/send", json=payload)

    assert response.status_code == 200
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    for kind in ("plain", "html"):
        content = message.get_body((kind,)).get_content()
        assert "Przybliżona lokalizacja zgłoszenia: nieokreślono" in content
        assert "google.com/maps" not in content


@pytest.mark.parametrize(
    "location",
    [
        {"longitude": 181, "latitude": 0},
        {"longitude": 0, "latitude": -91},
        {"longitude": 0},
        {"latitude": 0},
        {},
        {"longitude": "NaN", "latitude": 0},
        {"longitude": 0, "latitude": "Infinity"},
        {"longitude": 0, "latitude": 0, "pin": "https://example.com"},
    ],
)
def test_invalid_location_blocks_sending(smtp: MagicMock, location):
    response = TestClient(app).post("/send", json=PAYLOAD | {"location": location})

    assert response.status_code == 422
    smtp.assert_not_called()


def test_payload_markdown_and_html_are_not_rendered(smtp: MagicMock):
    description = '**bold** [link](https://example.com) <img src="https://example.com/pixel"> & {reporter}'
    response = TestClient(app).post(
        "/send", json=PAYLOAD | {"description": description, "first_name": "<b>Jan</b>", "last_name": "**Kowalski**"}
    )

    assert response.status_code == 200
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert description in message.get_body(("plain",)).get_content()
    html = message.get_body(("html",)).get_content()
    assert "**bold** [link](https://example.com)" in html
    assert "<strong>bold</strong>" not in html
    assert "<img " not in html
    assert "&lt;img src=&quot;https://example.com/pixel&quot;&gt; &amp; {reporter}" in html
    assert "&lt;b&gt;Jan&lt;/b&gt; **Kowalski**" in html


PHOTO_KEY = "reports/9a2b8c44-7d5e-4f10-a3b1-6c0d1e2f3a44/c3d4e5f6-1a2b-4c3d-8e9f-0a1b2c3d4e5f.png"


@pytest.fixture
def photo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    ("extension", "content", "media_type"),
    [
        ("jpg", b"\xff\xd8\xfftest", "image/jpeg"),
        ("png", b"\x89PNG\r\n\x1a\ntest", "image/png"),
        ("webp", b"RIFF\x00\x00\x00\x00WEBPtest", "image/webp"),
    ],
)
def test_photos_attach_existing_api_files(
    smtp: MagicMock, photo_root: Path, extension: str, content: bytes, media_type: str
):
    key = PHOTO_KEY.removesuffix("png") + extension
    path = photo_root / key
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    photo = {
        "id": path.stem,
        "report_id": path.parent.name,
        "storage_key": key,
        "created_at": "2026-10-04T00:00:00Z",
        "url": f"/photos/{path.stem}/file",
    }

    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [photo]})

    assert response.status_code == 200
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == media_type
    assert attachments[0].get_content_disposition() == "attachment"
    assert attachments[0].get_filename() == path.name
    assert attachments[0].get_payload(decode=True) == content
    assert message.get_body(("plain",)) is not None
    assert message.get_body(("html",)) is not None
    assert path.read_bytes() == content


def test_generated_photo_key_is_accepted(smtp: MagicMock, photo_root: Path):
    key = PHOTO_KEY.removesuffix(".png") + "_generated_7e8d9c0b-1a2f-4b3c-8d9e-0f1a2b3c4d5e.png"
    path = photo_root / key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\nimage")

    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": key}]})

    assert response.status_code == 200
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == path.name
    assert attachment.get_payload(decode=True) == b"\x89PNG\r\n\x1a\nimage"


@pytest.mark.parametrize(
    "key", ["/etc/passwd", "../secret.png", PHOTO_KEY.replace("reports/", "uploads/"), "https://example.com/photo.png"]
)
def test_invalid_photo_keys_block_sending(smtp: MagicMock, key: str):
    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": key}]})

    assert response.status_code == 422
    smtp.assert_not_called()


def test_too_many_photos_block_sending(smtp: MagicMock):
    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": PHOTO_KEY}] * 7})

    assert response.status_code == 422
    smtp.assert_not_called()


def test_saved_visualization_attachment(smtp: MagicMock, photo_root: Path):
    key = "visualizations/11111111-1111-4111-8111-111111111111/result.png"
    path = photo_root / key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\nvisualization")
    assert TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": key}]}).status_code == 200
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert next(message.iter_attachments()).get_payload(decode=True) == path.read_bytes()


def test_missing_photo_blocks_sending(smtp: MagicMock, photo_root: Path):
    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": PHOTO_KEY}]})

    assert response.status_code == 404
    assert response.json() == {"detail": "Photo not found"}
    smtp.assert_not_called()


def test_photo_symlink_cannot_leave_upload_directory(smtp: MagicMock, photo_root: Path):
    secret = photo_root.parent / "outside-photo.png"
    secret.write_bytes(b"\x89PNG\r\n\x1a\nprivate")
    path = photo_root / PHOTO_KEY
    path.parent.mkdir(parents=True)
    path.symlink_to(secret)

    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": PHOTO_KEY}]})

    assert response.status_code == 422
    smtp.assert_not_called()


@pytest.mark.parametrize(("content", "status"), [(b"invalid", 422), (b"\x89PNG\r\n\x1a\nlarge", 413)])
def test_invalid_photo_content_blocks_sending(
    smtp: MagicMock, photo_root: Path, monkeypatch: pytest.MonkeyPatch, content: bytes, status: int
):
    monkeypatch.setattr(storage, "MAX_PHOTO_BYTES", 10)
    path = photo_root / PHOTO_KEY
    path.parent.mkdir(parents=True)
    path.write_bytes(content)

    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": PHOTO_KEY}]})

    assert response.status_code == status
    smtp.assert_not_called()


def test_attachment_total_limit_blocks_sending(smtp: MagicMock, photo_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage, "MAX_ATTACHMENT_BYTES", 20)
    path = photo_root / PHOTO_KEY
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\ntest")

    response = TestClient(app).post("/send", json=PAYLOAD | {"photos": [{"storage_key": PHOTO_KEY}] * 2})

    assert response.status_code == 413
    smtp.assert_not_called()


def test_local_upload_directory_matches_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UPLOAD_DIR", "uploads")
    expected = Path(__file__).resolve().parents[2] / "api" / "uploads"

    assert storage.upload_dir() == expected
