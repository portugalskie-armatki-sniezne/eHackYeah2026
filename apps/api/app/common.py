from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated, Any, Generic, TypeVar

import psycopg
from fastapi import Depends, HTTPException, Query, status
from psycopg import sql
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db import get_connection

T = TypeVar("T")

Connection = Annotated[psycopg.Connection, Depends(get_connection)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]

# a WGS 84 point from longitude and latitude parameters, in this order.
POINT = sql.SQL("ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography")
NAMED_POINT = sql.SQL("ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326)::geography")


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitude: Longitude
    latitude: Latitude


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


def location_json(alias: str) -> sql.Composable:
    # returns the location column of a table alias as {"longitude": ..., "latitude": ...}.
    return sql.SQL(
        "json_build_object('longitude', ST_X({0}.location::geometry), 'latitude', ST_Y({0}.location::geometry))"
    ).format(sql.Identifier(alias))


@dataclass
class Near:
    longitude: float
    latitude: float
    radius_m: float

    def condition(self, alias: str) -> sql.Composable:
        return sql.SQL("ST_DWithin({}.location, {}, %(radius_m)s)").format(sql.Identifier(alias), NAMED_POINT)

    def params(self) -> dict[str, float]:
        return {"longitude": self.longitude, "latitude": self.latitude, "radius_m": self.radius_m}


def near_query(
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    radius_m: Annotated[float | None, Query(gt=0, le=100_000)] = None,
) -> Near | None:
    values = (longitude, latitude, radius_m)
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "longitude, latitude, and radius_m are required together"
        )
    return Near(longitude, latitude, radius_m)


NearFilter = Annotated[Near | None, Depends(near_query)]


def fetch_page(
    connection: psycopg.Connection,
    columns: sql.Composable,
    source: sql.Composable,
    conditions: list[sql.Composable],
    params: dict[str, Any],
    order_by: sql.Composable,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, Any]]]:
    """count and fetch one page, all queries use named parameters from params."""
    where = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions) if conditions else sql.SQL("")
    with connection.transaction():
        total = connection.execute(
            sql.SQL("SELECT count(*) AS total FROM {}{}").format(source, where), params
        ).fetchone()["total"]
        rows = connection.execute(
            sql.SQL("SELECT {} FROM {}{} ORDER BY {} LIMIT %(limit)s OFFSET %(offset)s").format(
                columns, source, where, order_by
            ),
            params | {"limit": limit, "offset": offset},
        ).fetchall()
    return total, rows


def assignments(changes: dict[str, Any]) -> tuple[sql.Composable, list[Any]]:
    """build a SET clause with positional parameters, location values are {"longitude", "latitude"}."""
    parts, params = [], []
    for column, value in changes.items():
        if column == "location":
            parts.append(sql.SQL("location = ") + POINT)
            params += [value["longitude"], value["latitude"]]
        else:
            parts.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
            params.append(value)
    return sql.SQL(", ").join(parts), params


def reject_nulls(model: BaseModel, fields: Iterable[str]) -> None:
    # PATCH fields are optional, but only nullable columns accept an explicit null.
    for field in fields:
        if field in model.model_fields_set and getattr(model, field) is None:
            raise ValueError(f"{field} cannot be null")


def foreign_key_error(error: psycopg.Error, messages: dict[str, str]) -> HTTPException:
    detail = messages.get(error.diag.constraint_name)
    if detail is None:
        raise error
    return HTTPException(status.HTTP_404_NOT_FOUND, detail)
