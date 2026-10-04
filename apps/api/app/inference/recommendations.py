"""recommend a service entity by its seat, without assigning responsibility."""

from dataclasses import dataclass
from typing import Literal

import psycopg
from psycopg import sql
from pydantic import BaseModel

from app import municipalities
from app.common import POINT, Location
from app.inference.entities import EntityClassificationRequest, EntityClassificationResult
from app.service_entities import ENTITY_COLUMNS, ServiceEntity
from app.service_entity_types import ServiceEntityType

MatchLevel = Literal["municipality", "county", "province", "nearest"]
MATCH_LEVELS: tuple[MatchLevel, ...] = ("municipality", "county", "province", "nearest")


class EntityRecommendationRequest(EntityClassificationRequest):
    location: Location


class ReportRegion(BaseModel):
    municipality_teryt: str
    municipality_name: str
    county_teryt: str
    county_name: str
    province_teryt: str


class RecommendedEntity(BaseModel):
    entity: ServiceEntity
    match_level: MatchLevel
    distance_m: float
    seat_location: Location
    seat_municipality_teryt: str


class EntityRecommendationResult(EntityClassificationResult):
    region: ReportRegion
    recommendation: RecommendedEntity | None
    candidates_count: int
    skipped_candidates_count: int


@dataclass(frozen=True)
class Candidate:
    entity: ServiceEntity
    location: Location
    municipality_teryt: str
    distance_m: float


def match_rank(report_teryt: str, seat_teryt: str) -> int:
    for rank, length in enumerate((7, 4, 2)):
        if report_teryt[:length] == seat_teryt[:length]:
            return rank
    return 3


def choose_candidate(
    candidates: list[Candidate], entity_type: ServiceEntityType, report_teryt: str
) -> RecommendedEntity | None:
    candidates = [
        candidate
        for candidate in candidates
        if candidate.entity.entity_type == entity_type and candidate.entity.is_active
    ]
    if not candidates:
        return None
    candidate = min(
        candidates,
        key=lambda item: (match_rank(report_teryt, item.municipality_teryt), item.distance_m, item.entity.id),
    )
    return RecommendedEntity(
        entity=candidate.entity,
        match_level=MATCH_LEVELS[match_rank(report_teryt, candidate.municipality_teryt)],
        distance_m=candidate.distance_m,
        seat_location=candidate.location,
        seat_municipality_teryt=candidate.municipality_teryt,
    )


def recommend_entity(
    connection: psycopg.Connection,
    classification: EntityClassificationResult,
    location: Location,
    municipality: municipalities.Municipality,
) -> EntityRecommendationResult:
    rows = connection.execute(
        sql.SQL(
            "SELECT {}, seat_teryt, ST_X(seat_location::geometry) AS longitude, "
            "ST_Y(seat_location::geometry) AS latitude, ST_Distance(seat_location, {}) AS distance_m, "
            "seat_address = jsonb_build_array(locality, street, house_number) AS current_address "
            "FROM service_entities WHERE entity_type = %s ORDER BY id"
        ).format(ENTITY_COLUMNS, POINT),
        (location.longitude, location.latitude, classification.entity_type),
    ).fetchall()
    candidates = [
        Candidate(
            ServiceEntity.model_validate(row),
            Location(longitude=row["longitude"], latitude=row["latitude"]),
            row["seat_teryt"],
            row["distance_m"],
        )
        for row in rows
        if row["is_active"] and row["current_address"] and row["distance_m"] is not None
    ]
    return EntityRecommendationResult(
        **classification.model_dump(),
        region=ReportRegion(
            municipality_teryt=municipality.teryt,
            municipality_name=municipality.name,
            county_teryt=municipality.county_teryt,
            county_name=municipality.county_name,
            province_teryt=municipality.teryt[:2],
        ),
        recommendation=choose_candidate(candidates, classification.entity_type, municipality.teryt),
        candidates_count=len(rows),
        skipped_candidates_count=len(rows) - len(candidates),
    )
