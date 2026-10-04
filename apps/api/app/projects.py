import math
import re
from collections import Counter
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
WORD = re.compile(r"[a-ząćęłńóśźż]{3,}", re.IGNORECASE)
# inflectional endings stripped by the light Polish stemmer, longest first
SUFFIXES = sorted(
    (
        "osciami osciach osciom osci osc "
        "owanie owania owaniu owaniem anie ania aniu aniem enie enia eniu eniem "
        "atywnymi atywnych atywnego atywnemu atywnej atywnym atywna atywne atywny atywni "
        "ywnymi ywnych ywnego ywnemu ywnej ywnym ywna ywne ywny ywni "
        "owych owego owemu owymi owej owym owa owe owy "
        "lbysmy lysmy lbym labym lismy "
        "ami ach ego emu ych ich ymi imi iej ow om ej ym im em ie ia iu ii "
        "ac ec ic yc y a e i u o"
    ).split(),
    key=len,
    reverse=True,
)
# weights of the innovation texts, the title and summary describe an innovation best
SEARCH_FIELDS = {
    "title": 3.0,
    "summary": 2.0,
    "category": 1.0,
    "description": 1.0,
    "problem": 1.0,
    "target_group": 1.0,
    "beneficiaries": 0.5,
    "effectiveness": 0.5,
}
# sections quoted as the matched snippet, in page order
SNIPPET_FIELDS = ("description", "problem", "target_group", "beneficiaries", "effectiveness")
# lower values let a single mention of a term count sooner
TERM_SATURATION = 0.5
# a query needs this much term weight to score fully, so a few common words cannot reach a high score
MIN_QUERY_WEIGHT = 8.0


def stem(word: str) -> str:
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            return word[: -len(suffix)]
    return word


def search_terms(text: str | None) -> list[str]:
    terms = []
    for word in WORD.findall(text or ""):
        normalized = word.lower().translate(ACCENTS_TRANS)
        if normalized not in STOP_WORDS:
            terms.append(stem(normalized))
    return terms


def score_projects(query: str, projects: list[dict]) -> list[tuple[float, dict]]:
    terms = list(dict.fromkeys(search_terms(query)))
    if not terms:
        return []

    weighted_terms: list[Counter[str]] = []
    for project in projects:
        frequencies: Counter[str] = Counter()
        for field, weight in SEARCH_FIELDS.items():
            for term in search_terms(project.get(field)):
                frequencies[term] += weight
        weighted_terms.append(frequencies)

    # rare terms tell innovations apart, while terms absent from the catalog cannot match anything
    total = len(projects)
    document_frequency = Counter(term for frequencies in weighted_terms for term in frequencies)
    weights = {
        term: math.log(1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
        for term in terms
        if document_frequency[term]
    }
    query_weight = max(sum(weights.values()), MIN_QUERY_WEIGHT)

    scored = []
    for project, frequencies in zip(projects, weighted_terms, strict=True):
        matched = sum(
            weight * frequencies[term] / (frequencies[term] + TERM_SATURATION)
            for term, weight in weights.items()
            if frequencies[term]
        )
        if matched:
            scored.append((matched / query_weight, project))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def extract_context_snippet(
    content: str | None,
    terms: set[str],
    window_before: int = 50,
    window_after: int = 150,
) -> str | None:
    if not content:
        return None

    clean = re.sub(r"\s+", " ", content).strip()
    if len(clean) < 40:
        return None

    best_pos = next(
        (
            match.start()
            for match in WORD.finditer(clean)
            if stem(match.group().lower().translate(ACCENTS_TRANS)) in terms
        ),
        -1,
    )
    if best_pos == -1:
        return None

    start = max(0, best_pos - window_before)
    end = min(len(clean), best_pos + window_after)

    if start > 0:
        space_idx = clean.find(" ", start)
        if space_idx != -1 and space_idx < best_pos:
            start = space_idx + 1

    if end < len(clean):
        space_idx = clean.rfind(" ", best_pos, end)
        if space_idx != -1 and space_idx > best_pos:
            end = space_idx

    snippet = clean[start:end].strip()
    if not snippet:
        return None

    if start > 0:
        snippet = "..." + snippet
    if end < len(clean):
        snippet = snippet + "..."

    words = re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}", snippet)
    if len(words) < 4:
        return None

    return snippet


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

    # the catalog holds about a hundred innovations, so term weights are computed per request
    cat_filter = sql.SQL("")
    if request.category:
        cat_filter = sql.SQL("WHERE (category = %(category)s OR category_slug = %(category)s) ")
        params["category"] = request.category

    query_sql = sql.SQL(
        "SELECT id, slug, title, category, category_slug, url, description, summary, "
        "       problem, target_group, beneficiaries, effectiveness "
        "FROM projects "
        "{cat_filter}"
        "ORDER BY id ASC"
    ).format(cat_filter=cat_filter)
    rows = connection.execute(query_sql, params).fetchall()

    terms = set(search_terms(request.query))
    results: list[ProjectSearchResult] = []
    for score, row in score_projects(request.query, rows)[: request.limit]:
        # quote the section that shares the most terms with the query
        sections = [row[field] for field in SNIPPET_FIELDS if row[field]]
        section = max(sections, key=lambda text: len(terms & set(search_terms(text))), default=None)
        results.append(
            ProjectSearchResult(
                id=row["id"],
                slug=row["slug"],
                title=row["title"],
                category=row["category"],
                category_slug=row["category_slug"],
                url=row["url"],
                description=row["description"],
                summary=row["summary"],
                matched_snippet=extract_context_snippet(section, terms),
                score=round(score, 2),
            )
        )
    return results
