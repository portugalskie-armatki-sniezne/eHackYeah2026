import smtplib
import ssl
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

PAYLOAD = {"to": "recipient@example.com", "subject": "Aktualizacja zgłoszenia", "text": "Zgłoszenie przyjęto."}


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-app-password")
    monkeypatch.setenv("SMTP_MOCK", "false")
    monkeypatch.delenv("SMTP_MOCK_DESTINATION", raising=False)
    smtp = MagicMock()
    monkeypatch.setattr("app.main.smtplib.SMTP", smtp)
    return smtp


def test_send_plaintext(smtp: MagicMock):
    response = TestClient(app).post("/send", json=PAYLOAD)

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
    assert message["To"] == PAYLOAD["to"]
    assert message["Subject"] == PAYLOAD["subject"]
    assert message.get_content_type() == "text/plain"
    assert not message.is_multipart()
    assert message.get_content().strip() == PAYLOAD["text"]
    assert connection.send_message.call_args.kwargs["to_addrs"] == [PAYLOAD["to"]]


@pytest.mark.parametrize("flag", ["true", "TRUE", " true "])
def test_mock_redirects_mail(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, flag: str):
    monkeypatch.setenv("SMTP_MOCK", flag)
    monkeypatch.setenv("SMTP_MOCK_DESTINATION", "team@example.com")

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 200
    connection = smtp.return_value.__enter__.return_value
    message = connection.send_message.call_args.args[0]
    assert message["To"] == "team@example.com"
    assert connection.send_message.call_args.kwargs["to_addrs"] == ["team@example.com"]
    assert message["Subject"] == PAYLOAD["subject"]
    assert message.get_content().strip() == PAYLOAD["text"]


@pytest.mark.parametrize("flag", ["false", None])
def test_disabled_mock_uses_requested_recipient(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, flag: str | None):
    if flag is None:
        monkeypatch.delenv("SMTP_MOCK")
    monkeypatch.setenv("SMTP_MOCK_DESTINATION", "team@example.com")

    response = TestClient(app).post("/send", json=PAYLOAD)

    assert response.status_code == 200
    connection = smtp.return_value.__enter__.return_value
    assert connection.send_message.call_args.args[0]["To"] == PAYLOAD["to"]
    assert connection.send_message.call_args.kwargs["to_addrs"] == [PAYLOAD["to"]]


@pytest.mark.parametrize("destination", [None, "", "invalid", "team@example.com, other@example.com"])
def test_mock_requires_valid_destination(smtp: MagicMock, monkeypatch: pytest.MonkeyPatch, destination: str | None):
    monkeypatch.setenv("SMTP_MOCK", "true")
    if destination is not None:
        monkeypatch.setenv("SMTP_MOCK_DESTINATION", destination)

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
        {"text": ""},
        {"html": "<p>Update</p>"},
    ],
)
def test_invalid_mail(smtp: MagicMock, values: dict[str, str]):
    response = TestClient(app).post("/send", json=PAYLOAD | values)

    assert response.status_code == 422
    smtp.assert_not_called()


def test_health_without_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
