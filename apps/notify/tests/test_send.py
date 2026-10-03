import smtplib
import ssl
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

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
    monkeypatch.setenv("SMTP_MOCK", "false")
    monkeypatch.delenv("SMTP_MOCK_DESTINATION", raising=False)
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
    assert message["To"] == PAYLOAD["to"]
    assert message["Subject"] == PAYLOAD["subject"]
    assert message.get_content_type() == "text/plain"
    assert not message.is_multipart()
    content = message.get_content()
    assert content.count(PAYLOAD["description"]) == 1
    assert intro in content
    assert other_intro not in content
    assert content.startswith("Szanowni Państwo,")
    assert "Zgłoszone przez: Jan Kowalski" in content
    assert content.rstrip().endswith("Zespół pomożeMy")
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
    assert message.get_content().count(PAYLOAD["description"]) == 1


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
    assert message.get_content_type() == "text/plain"
    assert message.get_content().count(description) == 1


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
    content = smtp.return_value.__enter__.return_value.send_message.call_args.args[0].get_content()
    assert "Zgłoszone przez: anonimowo" in content
    assert "Jan" not in content
    assert "Kowalski" not in content
    assert content.count(PAYLOAD["description"]) == 1


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
    content = smtp.return_value.__enter__.return_value.send_message.call_args.args[0].get_content()
    assert "Zgłoszone przez: Łukasz Żółć-{description}\n" in content
    assert content.count(PAYLOAD["description"]) == 1


def test_health_without_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
