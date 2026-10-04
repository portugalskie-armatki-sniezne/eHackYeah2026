import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode

import markdown
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

from app import storage

app = FastAPI(title="eHackYeah2026 Notify")
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\r\n]+$")]


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class Photo(BaseModel):
    storage_key: str = Field(
        pattern=r"^reports/[0-9a-f-]{36}/[0-9a-f-]{36}(?:_generated(?:_[0-9a-f-]{36})?)?\.(jpg|png|webp)$"
    )


class Mail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: EmailStr
    subject: str = Field(min_length=1, max_length=255, pattern=r"^[^\r\n]+$")
    description: str = Field(min_length=1)
    report_type: Literal["issue", "improvement"]
    first_name: Name | None = None
    last_name: Name | None = None
    anonymous: bool = Field(default=False, strict=True)
    location: Location | None = None
    photos: list[Photo] = Field(default_factory=list, max_length=6)

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
    template = (TEMPLATES_DIR / f"{payload.report_type}.md").read_text(encoding="utf-8")
    reporter = "anonimowo" if payload.anonymous else f"{payload.first_name} {payload.last_name}"
    pin = "nieokreślono"
    if payload.location is not None:
        query = urlencode({"api": 1, "query": f"{payload.location.latitude},{payload.location.longitude}"})
        pin = f"https://www.google.com/maps/search/?{query}"
    message.set_content(template.replace("**", "").format(description=payload.description, reporter=reporter, pin=pin))
    html_pin = f'<a href="{escape(pin)}">{escape(pin)}</a>' if payload.location is not None else pin
    html = markdown.markdown(template, extensions=["nl2br"]).format(
        description=escape(payload.description).replace("\n", "<br>\n"),
        reporter=escape(reporter),
        pin=html_pin,
    )
    message.add_alternative(html, subtype="html")

    total_bytes = 0
    for photo in payload.photos:
        media_type, data = storage.read_photo(photo.storage_key)
        total_bytes += len(data)
        if total_bytes > storage.MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail="Photos can have at most 20 MB in total")
        message.add_attachment(data, maintype="image", subtype=media_type, filename=Path(photo.storage_key).name)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(username, password)
            smtp.send_message(message, to_addrs=[destination])
    except (smtplib.SMTPException, OSError) as error:
        raise HTTPException(status_code=502, detail="SMTP delivery failed") from error

    return {"status": "sent"}
