from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from psycopg import sql
from pydantic import BaseModel

from app.common import Connection, Limit, Offset, Page, fetch_page

router = APIRouter(prefix="/service-entities", tags=["service entities"])

ServiceEntityType = Literal[
    "road_manager",
    "transport_authority",
    "transport_operator",
    "green_space_manager",
    "water_infrastructure_manager",
    "water_sewage_utility",
    "water_sewage_authority",
    "heating_utility",
    "waste_management",
    "municipal_services",
    "municipal_guard",
    "housing_manager",
    "cemetery_manager",
    "sports_infrastructure_manager",
    "municipal_investment",
]

ENTITY_TYPE_DESCRIPTION = (
    "Typ jednostki, dopasowanie dokładne: "
    "road_manager - zarządca dróg; transport_authority - organizator transportu; "
    "transport_operator - operator przewozów; green_space_manager - zarządca zieleni; "
    "water_infrastructure_manager - zarządca infrastruktury wodnej i odwodnienia; "
    "water_sewage_utility - przedsiębiorstwo wodociągowo-kanalizacyjne; "
    "water_sewage_authority - związek JST ds. wodociągów i kanalizacji; "
    "heating_utility - przedsiębiorstwo ciepłownicze; waste_management - oczyszczanie i odpady; "
    "municipal_services - zakład lub przedsiębiorstwo komunalne; municipal_guard - straż miejska lub gminna; "
    "housing_manager - zarządca budynków i mienia komunalnego; cemetery_manager - zarządca cmentarzy; "
    "sports_infrastructure_manager - zarządca infrastruktury sportowej; "
    "municipal_investment - jednostka inwestycji miejskich. Typ nie określa kompletu kompetencji jednostki."
)


class ServiceEntity(BaseModel):
    id: int
    source_key: str
    name: str
    short_name: str | None
    entity_type: ServiceEntityType
    teryt_code: str | None
    locality: str | None
    postal_code: str | None
    street: str | None
    house_number: str | None
    phone_number: str | None
    email: str | None
    website: str | None
    bip_url: str | None
    reporting_channel: str | None
    reporting_channel_description: str | None
    source_urls: list[str]
    verified_on: date


ENTITY_COLUMNS = sql.SQL(", ").join(sql.Identifier(field) for field in ServiceEntity.model_fields)


@router.get("", description="Publiczny katalog jednostek usługowych, tylko do odczytu. Wyniki są sortowane po id.")
def list_service_entities(
    connection: Connection,
    entity_type: Annotated[ServiceEntityType | None, Query(description=ENTITY_TYPE_DESCRIPTION)] = None,
    teryt_code: Annotated[
        str | None,
        Query(description="Dokładny kod TERYT powiązanej gminy. Nie określa zasięgu usług ani jurysdykcji jednostki."),
    ] = None,
    locality: Annotated[str | None, Query(description="Dokładna nazwa miejscowości siedziby lub oddziału.")] = None,
    q: Annotated[
        str | None,
        Query(description="Fragment nazwy lub skrótu jednostki, bez rozróżniania wielkości liter. % i _ są dosłowne."),
    ] = None,
    limit: Annotated[Limit, Query(description="Liczba wyników na stronie, od 1 do 200.")] = 50,
    offset: Annotated[Offset, Query(description="Liczba wyników do pominięcia.")] = 0,
) -> Page[ServiceEntity]:
    conditions, params = [], {}
    for column, value in (("entity_type", entity_type), ("teryt_code", teryt_code), ("locality", locality)):
        if value is not None:
            conditions.append(sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
            params[column] = value
    if q:
        conditions.append(sql.SQL("(name ILIKE %(q)s ESCAPE '\\' OR short_name ILIKE %(q)s ESCAPE '\\')"))
        params["q"] = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    total, rows = fetch_page(
        connection,
        ENTITY_COLUMNS,
        sql.SQL("service_entities"),
        conditions,
        params,
        sql.SQL("id"),
        limit,
        offset,
    )
    return Page[ServiceEntity](
        items=[ServiceEntity.model_validate(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{entity_id}", responses={404: {"description": "Nie znaleziono jednostki usługowej."}})
def get_service_entity(entity_id: int, connection: Connection) -> ServiceEntity:
    row = connection.execute(
        sql.SQL("SELECT {} FROM service_entities WHERE id = %s").format(ENTITY_COLUMNS), (entity_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service entity not found")
    return ServiceEntity.model_validate(row)
