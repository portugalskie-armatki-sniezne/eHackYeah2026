from fastapi import APIRouter, HTTPException, status
from psycopg import sql
from pydantic import BaseModel

from app.common import Connection, Limit, Offset, Page, fetch_page

router = APIRouter(prefix="/institution-contacts", tags=["institution contacts"])


class InstitutionContact(BaseModel):
    id: int
    teryt_code: str
    local_government_name: str
    province: str | None
    county: str | None
    local_government_type: str | None
    office_name: str | None
    locality: str | None
    postal_code: str | None
    post_office: str | None
    street: str | None
    house_number: str | None
    phone_area_code: str | None
    phone_number: str | None
    alternate_phone_number: str | None
    phone_extension: str | None
    fax_area_code: str | None
    fax_number: str | None
    fax_extension: str | None
    email: str | None
    website: str | None
    electronic_inbox: str | None
    electronic_delivery_address: str | None


INSTITUTION_COLUMNS = sql.SQL(", ").join(sql.Identifier(field) for field in InstitutionContact.model_fields)


@router.get("")
def list_institution_contacts(
    connection: Connection,
    teryt_code: str | None = None,
    province: str | None = None,
    county: str | None = None,
    local_government_type: str | None = None,
    q: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[InstitutionContact]:
    conditions, params = [], {}
    for column, value in (("teryt_code", teryt_code), ("province", province), ("county", county),
                          ("local_government_type", local_government_type)):
        if value is not None:
            conditions.append(sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
            params[column] = value
    if q:
        # q matches a fragment of the authority name, % and _ are matched literally.
        conditions.append(sql.SQL("local_government_name ILIKE %(q)s ESCAPE '\\'"))
        params["q"] = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    total, rows = fetch_page(connection, INSTITUTION_COLUMNS, sql.SQL("institution_contacts"), conditions,
                             params, sql.SQL("id"), limit, offset)
    return Page[InstitutionContact](items=[InstitutionContact.model_validate(row) for row in rows],
                                    total=total, limit=limit, offset=offset)


@router.get("/{institution_id}")
def get_institution_contact(institution_id: int, connection: Connection) -> InstitutionContact:
    row = connection.execute(
        sql.SQL("SELECT {} FROM institution_contacts WHERE id = %s").format(INSTITUTION_COLUMNS),
        (institution_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution not found")
    return InstitutionContact.model_validate(row)
