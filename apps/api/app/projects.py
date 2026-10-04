import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from psycopg import sql
from pydantic import BaseModel, Field

from app.common import Connection, Limit, Offset, Page, fetch_page

router = APIRouter(prefix="/projects", tags=["projects"])

STOP_WORDS = {
    "a",
    "aby",
    "ale",
    "bardzo",
    "bez",
    "bo",
    "by",
    "byl",
    "byla",
    "byli",
    "bylo",
    "byc",
    "chce",
    "chcecie",
    "chcemy",
    "chcialbym",
    "chcialabym",
    "chca",
    "co",
    "coraz",
    "cos",
    "czy",
    "dla",
    "do",
    "gdzie",
    "go",
    "i",
    "ich",
    "im",
    "ja",
    "jak",
    "jaka",
    "jaki",
    "jakie",
    "jako",
    "jest",
    "jestem",
    "jestesmy",
    "jeszcze",
    "juz",
    "kiedy",
    "kto",
    "ktora",
    "ktore",
    "ktory",
    "lub",
    "ma",
    "maja",
    "mamy",
    "miejsce",
    "miejsca",
    "miejscu",
    "mnie",
    "moga",
    "moze",
    "mozna",
    "my",
    "na",
    "nad",
    "nam",
    "nami",
    "nas",
    "nasz",
    "nasza",
    "nasze",
    "nie",
    "nowe",
    "nowa",
    "nowy",
    "o",
    "od",
    "on",
    "ona",
    "oni",
    "ono",
    "oraz",
    "po",
    "pod",
    "przed",
    "przez",
    "przy",
    "robic",
    "sie",
    "stworzyc",
    "stworzenie",
    "ta",
    "tak",
    "taki",
    "takze",
    "tam",
    "te",
    "tego",
    "tej",
    "temu",
    "ten",
    "to",
    "tutaj",
    "twoj",
    "twoja",
    "twoje",
    "ty",
    "tylko",
    "w",
    "we",
    "wiec",
    "wszystko",
    "wraz",
    "z",
    "za",
    "ze",
    "zeby",
    "zrobic",
}
ACCENTS_TRANS = str.maketrans("ąćęłńóśźż", "acelnoszz")


def extract_keywords(query: str) -> list[str]:
    raw_words = re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}", query.lower())
    clean_words = []
    for word in raw_words:
        normalized = word.translate(ACCENTS_TRANS)
        if normalized not in STOP_WORDS:
            clean_words.append(word)
    return clean_words


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
    params: dict[str, object] = {"limit": request.limit}

    # if vector is provided, execute cosine similarity search on summary_vector
    if request.query_vector and len(request.query_vector) == 1024:
        cat_filter = sql.SQL("")
        if request.category:
            cat_filter = sql.SQL("WHERE (category = %(category)s OR category_slug = %(category)s) ")
            params["category"] = request.category

        query_sql = sql.SQL(
            "SELECT id, slug, title, category, category_slug, url, description, summary, "
            "       NULL AS matched_snippet, "
            "       round((1 - (summary_vector <=> %(vector)s::vector))::numeric, 4)::float AS score "
            "FROM projects "
            "{cat_filter}"
            "ORDER BY summary_vector <=> %(vector)s::vector ASC "
            "LIMIT %(limit)s"
        ).format(cat_filter=cat_filter)
        params["vector"] = "[" + ",".join(str(val) for val in request.query_vector) + "]"
        rows = connection.execute(query_sql, params).fetchall()
        return [ProjectSearchResult.model_validate(row) for row in rows]

    keywords = extract_keywords(request.query)
    if not keywords:
        return []

    # extract stems of keywords for Polish grammatical inflection tolerance
    stems = [w[:5] if len(w) >= 5 else w for w in keywords]
    patterns = [f"%{s}%" for s in stems]

    cat_filter = sql.SQL("")
    params["patterns"] = patterns
    if request.category:
        cat_filter = sql.SQL("AND (p.category = %(category)s OR p.category_slug = %(category)s) ")
        params["category"] = request.category

    query_sql = sql.SQL(
        "SELECT p.id, p.slug, p.title, p.category, p.category_slug, p.url, p.description, p.summary, "
        "       ( "
        "           SELECT substring(c.content from 1 for 300) "
        "           FROM project_chunks c "
        "           WHERE c.project_slug = p.slug AND c.content ILIKE ANY(%(patterns)s) "
        "           LIMIT 1 "
        "       ) AS matched_snippet "
        "FROM projects p "
        "WHERE (p.title ILIKE ANY(%(patterns)s) "
        "   OR p.summary ILIKE ANY(%(patterns)s) "
        "   OR coalesce(p.category, '') ILIKE ANY(%(patterns)s)) "
        "{cat_filter}"
    ).format(cat_filter=cat_filter)

    rows = connection.execute(query_sql, params).fetchall()

    scored_results: list[ProjectSearchResult] = []
    for row in rows:
        title_l = row["title"].lower()
        cat_l = (row["category"] or "").lower()
        sum_l = row["summary"].lower()

        score = 0.0
        matched_count = 0
        for stem in stems:
            if stem in title_l:
                score += 0.40
                matched_count += 1
            elif stem in cat_l:
                score += 0.30
                matched_count += 1
            elif stem in sum_l:
                score += 0.15
                matched_count += 1

        if matched_count >= 2:
            score += 0.15 * (matched_count - 1)

        final_score = min(0.96, round(score, 2))
        snippet = row["matched_snippet"] or row["description"] or row["summary"]
        if snippet and len(snippet) > 300:
            snippet = snippet[:300] + "..."

        scored_results.append(
            ProjectSearchResult(
                id=row["id"],
                slug=row["slug"],
                title=row["title"],
                category=row["category"],
                category_slug=row["category_slug"],
                url=row["url"],
                description=row["description"],
                summary=row["summary"],
                matched_snippet=snippet,
                score=final_score,
            )
        )

    scored_results.sort(key=lambda r: r.score, reverse=True)
    return scored_results[: request.limit]
