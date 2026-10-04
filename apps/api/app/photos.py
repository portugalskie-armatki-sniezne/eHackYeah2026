from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, computed_field

from app import storage
from app.common import Connection

router = APIRouter(prefix="/photos", tags=["photos"])

PHOTO_COLUMNS = "p.id, p.report_id, p.storage_key, p.created_at"
PHOTO_ORDER = "p.created_at, p.id"


def photo_file_url(photo_id: UUID) -> str:
    # relative to the API base URL and public, so the app can show photos without a token.
    return f"/photos/{photo_id}/file"


class Photo(BaseModel):
    id: UUID
    report_id: UUID
    storage_key: str
    created_at: datetime

    @computed_field
    @property
    def url(self) -> str:
        return photo_file_url(self.id)


@router.get("/{photo_id}/file", response_class=FileResponse)
def get_photo_file(photo_id: UUID, connection: Connection) -> FileResponse:
    row = connection.execute("SELECT storage_key FROM report_photos WHERE id = %s", (photo_id,)).fetchone()
    path = storage.file_path(row["storage_key"]) if row else None
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return FileResponse(path, media_type=storage.media_type(row["storage_key"]))
