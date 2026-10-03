import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from psycopg import sql
from pydantic import BaseModel

Role = Literal["user", "office", "admin"]

USER_COLUMNS = sql.SQL("id, first_name, last_name, email, phone, role, edited_at, created_at")


def normalize_phone(phone: str) -> str:
    # store one form per number so the unique constraint and phone login work.
    return re.sub(r"[\s-]", "", phone)


class User(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    role: Role
    edited_at: datetime
    created_at: datetime
