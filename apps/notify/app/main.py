import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

app = FastAPI(title="eHackYeah2026 Notify")
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\r\n]+$")]


class Mail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: EmailStr
    subject: str = Field(min_length=1, max_length=255, pattern=r"^[^\r\n]+$")
    description: str = Field(min_length=1)
    report_type: Literal["issue", "improvement"]
    first_name: Name | None = None
    last_name: Name | None = None
    anonymous: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def require_reporter(self) -> "Mail":
        if not self.anonymous and (self.first_name is None or self.last_name is None):
            raise ValueError("first_name and last_name are required unless anonymous is true")
        return self


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/send")
def send(payload: Mail) -> dict[str, str]:
    username = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    if not username or not password:
        raise HTTPException(status_code=503, detail="SMTP credentials are not configured")

    mock = os.environ.get("SMTP_MOCK", "false").strip().lower()
    if mock not in {"true", "false"}:
        raise HTTPException(status_code=503, detail="SMTP_MOCK must be true or false")
    destination = str(payload.to)
    if mock == "true":
        try:
            destination = TypeAdapter(EmailStr).validate_python(os.environ.get("SMTP_MOCK_DESTINATION", ""))
        except ValidationError as error:
            raise HTTPException(status_code=503, detail="SMTP mock destination is not configured or invalid") from error

    message = EmailMessage()
    message["From"] = username
    message["To"] = destination
    message["Subject"] = payload.subject
    template = (TEMPLATES_DIR / f"{payload.report_type}.txt").read_text(encoding="utf-8")
    reporter = "anonimowo" if payload.anonymous else f"{payload.first_name} {payload.last_name}"
    message.set_content(template.format(description=payload.description, reporter=reporter))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(username, password)
            smtp.send_message(message, to_addrs=[destination])
    except (smtplib.SMTPException, OSError) as error:
        raise HTTPException(status_code=502, detail="SMTP delivery failed") from error

    return {"status": "sent"}
