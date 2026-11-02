import os
from dataclasses import dataclass

from pydantic import EmailStr, TypeAdapter, ValidationError


def positive_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be a positive integer") from None
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class Settings:
    gemini_user_limit: int
    smtp_user_limit: int
    window_seconds: int
    draft_ttl_days: int
    gemini_url: str
    notify_url: str


def settings() -> Settings:
    return Settings(
        positive_int("GEMINI_USER_LIMIT", 50),
        positive_int("SMTP_USER_LIMIT", 50),
        positive_int("RATE_LIMIT_WINDOW_SECONDS", 86400),
        positive_int("VISUALIZATION_DRAFT_TTL_DAYS", 7),
        os.environ.get("GEMINI_URL", "http://127.0.0.1:8002").rstrip("/"),
        os.environ.get("NOTIFY_URL", "http://127.0.0.1:8001").rstrip("/"),
    )


def smtp_destination() -> str:
    if os.environ.get("SMTP_MOCK", "").strip().lower() != "true":
        raise ValueError("SMTP_MOCK must be true during the hackathon")
    try:
        return str(TypeAdapter(EmailStr).validate_python(os.environ.get("SMTP_MOCK_DESTINATION", "")))
    except ValidationError:
        raise ValueError("SMTP_MOCK_DESTINATION must be a valid test address") from None
