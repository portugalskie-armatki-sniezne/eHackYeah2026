import os
import smtplib
import ssl
from email.message import EmailMessage

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, ValidationError

app = FastAPI(title="eHackYeah2026 Notify")


class Mail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: EmailStr
    subject: str = Field(min_length=1, max_length=255, pattern=r"^[^\r\n]+$")
    text: str = Field(min_length=1)


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
    message.set_content(payload.text)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(username, password)
            smtp.send_message(message, to_addrs=[destination])
    except (smtplib.SMTPException, OSError) as error:
        raise HTTPException(status_code=502, detail="SMTP delivery failed") from error

    return {"status": "sent"}
