import os
from pathlib import Path

from fastapi import HTTPException

MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_TOTAL_PHOTO_BYTES = 20 * 1024 * 1024


def upload_dir() -> Path:
    path = Path(os.environ.get("UPLOAD_DIR") or "uploads")
    return path if path.is_absolute() else Path(__file__).resolve().parents[2] / "api" / path


def read_photo(storage_key: str) -> tuple[str, bytes]:
    root = upload_dir().resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=422, detail="Invalid photo storage key")
    try:
        with path.open("rb") as file:
            data = file.read(MAX_PHOTO_BYTES + 1)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Photo not found") from error
    except OSError as error:
        raise HTTPException(status_code=503, detail="Photo cannot be read") from error
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="A photo can have at most 10 MB")
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", data
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", data
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", data
    raise HTTPException(status_code=422, detail="Photos must be JPEG, PNG, or WebP images")
