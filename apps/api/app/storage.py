import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTOS_PER_REPORT = 5
MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def upload_dir() -> Path:
    # relative paths start in apps/api, the default directory is ignored by Git.
    path = Path(os.environ.get("UPLOAD_DIR") or "uploads")
    return path if path.is_absolute() else Path(__file__).resolve().parent.parent / path


def check_upload_dir() -> None:
    """create the upload directory and fail at startup when photos cannot be saved there."""
    path = upload_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
    except OSError as error:
        raise RuntimeError(f"UPLOAD_DIR {path} is not writable: {error.strerror or error}") from None


def file_path(storage_key: str) -> Path:
    return upload_dir() / storage_key


def detect_extension(data: bytes) -> str | None:
    # the type comes from the file header, not from the client's file name or content type.
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def media_type(storage_key: str) -> str:
    return MEDIA_TYPES.get(storage_key.rsplit(".", 1)[-1], "application/octet-stream")


def save(storage_key: str, data: bytes) -> None:
    path = file_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def move(source_key: str, target_key: str) -> None:
    """rename a saved file, for a photo that moves from one key to another."""
    target = file_path(target_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    file_path(source_key).replace(target)


def delete(storage_keys: Iterable[str]) -> None:
    for storage_key in storage_keys:
        path = file_path(storage_key)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass


@contextmanager
def cleanup_on_error() -> Iterator[list[str]]:
    """collect saved storage keys and delete their files if the block fails."""
    saved: list[str] = []
    try:
        yield saved
    except BaseException:
        delete(saved)
        raise
