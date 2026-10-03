from fastapi import APIRouter
from pydantic import BaseModel

from app.common import Connection

router = APIRouter(tags=["reference data"])


class ReferenceItem(BaseModel):
    id: int
    name: str


@router.get("/report-categories")
def list_report_categories(connection: Connection) -> list[ReferenceItem]:
    rows = connection.execute("SELECT id, name FROM report_categories ORDER BY id").fetchall()
    return [ReferenceItem.model_validate(row) for row in rows]


@router.get("/master-report-statuses")
def list_master_report_statuses(connection: Connection) -> list[ReferenceItem]:
    rows = connection.execute("SELECT id, name FROM master_report_statuses ORDER BY id").fetchall()
    return [ReferenceItem.model_validate(row) for row in rows]
