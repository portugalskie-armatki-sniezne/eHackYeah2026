from datetime import datetime
from typing import Literal
from uuid import UUID

from psycopg import sql
from pydantic import BaseModel

Role = Literal["user", "office", "admin"]

USER_COLUMNS = sql.SQL("id, first_name, last_name, email, phone, role, created_at")


class User(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    role: Role
    created_at: datetime
