from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from psycopg import sql
from pydantic import BaseModel, Field

from app.common import Connection, Limit, Offset, Page, fetch_page

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectSummary(BaseModel):
    id: int
    slug: str
    title: str
    category: str
    category_slug: str | None = None
    url: str
    description: str | None = None
    problem: str | None = None
    target_group: str | None = None
    beneficiaries: str | None = None
    effectiveness: str | None = None
    authors: str | None = None
    summary: str
    created_at: datetime


class ProjectCategory(BaseModel):
    category: str
    category_slug: str | None = None
    count: int


class ProjectSearchQuery(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=1000, description="Wyszukiwana fraza lub opis inicjatywy")]
    query_vector: list[float] | None = Field(default=None, description="Opcjonalny 1024-wymiarowy wektor zapytania")
    category: str | None = Field(default=None, description="Opcjonalne filtrowanie po kategorii lub category_slug")
    limit: Annotated[int, Field(ge=1, le=20)] = 5


class ProjectSearchResult(BaseModel):
    id: int
    slug: str
    title: str
    category: str
    category_slug: str | None = None
    url: str
    description: str | None = None
    summary: str
    matched_snippet: str | None = None
    score: float


PROJECT_COLUMNS = sql.SQL(", ").join(sql.Identifier(field) for field in ProjectSummary.model_fields)


@router.get("", description="Pobierz listę projektów ROPS z opcjonalnym filtrowaniem po kategorii")
def list_projects(
    connection: Connection,
    category: Annotated[str | None, Query(description="Kategoria lub slug kategorii")] = None,
    q: Annotated[str | None, Query(description="Fraza wyszukiwana w tytule, opisie lub podsumowaniu")] = None,
    limit: Annotated[Limit, Query(description="Liczba wyników na stronę, od 1 do 200")] = 50,
    offset: Annotated[Offset, Query(description="Liczba pomijanych wyników")] = 0,
) -> Page[ProjectSummary]:
    conditions: list[sql.Composable] = []
    params: dict[str, object] = {}

    if category is not None:
        conditions.append(sql.SQL("(category = %(category)s OR category_slug = %(category)s)"))
        params["category"] = category

    if q:
        escaped_q = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(sql.SQL("(title ILIKE %(q)s ESCAPE '\\' OR summary ILIKE %(q)s ESCAPE '\\')"))
        params["q"] = escaped_q

    total, rows = fetch_page(
        connection,
        columns=PROJECT_COLUMNS,
        source=sql.Identifier("projects"),
        conditions=conditions,
        params=params,
        order_by=sql.SQL("id ASC"),
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[ProjectSummary.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/categories", description="Pobierz unikalne kategorie projektów ROPS wraz z liczbą projektów")
def list_categories(connection: Connection) -> list[ProjectCategory]:
    rows = connection.execute(
        "SELECT category, category_slug, count(*) AS count "
        "FROM projects "
        "GROUP BY category, category_slug "
        "ORDER BY count DESC, category ASC"
    ).fetchall()
    return [ProjectCategory.model_validate(row) for row in rows]


@router.get("/{slug}", description="Pobierz szczegóły pojedynczego projektu ROPS")
def get_project(connection: Connection, slug: str) -> ProjectSummary:
    row = connection.execute(
        sql.SQL("SELECT {} FROM projects WHERE slug = %(slug)s").format(PROJECT_COLUMNS),
        {"slug": slug},
    ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return ProjectSummary.model_validate(row)


@router.post("/search", description="Wyszukiwanie podobnych innowacji społecznych w bazie wektorowej i pełnotekstowej")
def search_projects(
    connection: Connection,
    request: ProjectSearchQuery,
) -> list[ProjectSearchResult]:
    # if vector is provided, execute cosine similarity search on summary_vector
    if request.query_vector and len(request.query_vector) == 1024:
        query_sql = sql.SQL(
            "SELECT id, slug, title, category, category_slug, url, description, summary, "
            "       NULL AS matched_snippet, "
            "       round((1 - (summary_vector <=> %(vector)s::vector))::numeric, 4)::float AS score "
            "FROM projects "
            "WHERE (%(category)s IS NULL OR category = %(category)s OR category_slug = %(category)s) "
            "ORDER BY summary_vector <=> %(vector)s::vector ASC "
            "LIMIT %(limit)s"
        )
        vector_str = "[" + ",".join(str(val) for val in request.query_vector) + "]"
        rows = connection.execute(
            query_sql,
            {
                "vector": vector_str,
                "category": request.category,
                "limit": request.limit,
            },
        ).fetchall()
        return [ProjectSearchResult.model_validate(row) for row in rows]

    # hybrid search with PostgreSQL text search and project_chunks snippet matching
    like_query = "%" + request.query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    query_sql = sql.SQL(
        "WITH matched_chunks AS ("
        "    SELECT project_slug, content, "
        "           ts_rank_cd(tsv, plainto_tsquery('polish', %(query)s)) AS chunk_score "
        "    FROM project_chunks "
        "    WHERE tsv @@ plainto_tsquery('polish', %(query)s) "
        "    ORDER BY chunk_score DESC "
        "    LIMIT 50"
        "), "
        "ranked_projects AS ("
        "    SELECT p.id, p.slug, p.title, p.category, p.category_slug, p.url, p.description, p.summary, "
        "           coalesce(max(mc.chunk_score), 0.0) AS chunk_score, "
        "           ts_rank_cd( "
        "               to_tsvector('polish', "
        "                   p.title || ' ' || p.category || ' ' || p.summary || ' ' || coalesce(p.description, '') "
        "               ), "
        "               plainto_tsquery('polish', %(query)s) "
        "           ) AS direct_score, "
        "           ( "
        "               SELECT mc2.content "
        "               FROM matched_chunks mc2 "
        "               WHERE mc2.project_slug = p.slug "
        "               ORDER BY mc2.chunk_score DESC "
        "               LIMIT 1 "
        "           ) AS matched_snippet "
        "    FROM projects p "
        "    LEFT JOIN matched_chunks mc ON mc.project_slug = p.slug "
        "    WHERE (%(category)s IS NULL OR p.category = %(category)s OR p.category_slug = %(category)s) "
        "    GROUP BY p.id, p.slug, p.title, p.category, p.category_slug, p.url, p.description, p.summary "
        ") "
        "SELECT id, slug, title, category, category_slug, url, description, summary, "
        "       substring(matched_snippet from 1 for 300) AS matched_snippet, "
        "       round((least(1.0, direct_score * 0.8 + chunk_score * 0.5 + "
        "             case when title ILIKE %(like_query)s then 0.4 else 0.0 end + "
        "             case when summary ILIKE %(like_query)s then 0.2 else 0.0 end))::numeric, 4)::float AS score "
        "FROM ranked_projects "
        "WHERE direct_score > 0 OR chunk_score > 0 OR title ILIKE %(like_query)s OR summary ILIKE %(like_query)s "
        "ORDER BY score DESC "
        "LIMIT %(limit)s"
    )
    rows = connection.execute(
        query_sql,
        {
            "query": request.query,
            "like_query": like_query,
            "category": request.category,
            "limit": request.limit,
        },
    ).fetchall()

    return [ProjectSearchResult.model_validate(row) for row in rows]
