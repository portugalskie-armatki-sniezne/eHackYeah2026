from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sample_projects(connection: psycopg.Connection):
    token = uuid4().hex[:8]
    connection.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    connection.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'polish') THEN "
        "CREATE TEXT SEARCH CONFIGURATION polish (COPY = simple); "
        "END IF; END $$;"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS projects ("
        "  id SERIAL PRIMARY KEY,"
        "  slug VARCHAR(255) UNIQUE NOT NULL,"
        "  title TEXT NOT NULL,"
        "  category TEXT NOT NULL,"
        "  category_slug VARCHAR(255),"
        "  url TEXT NOT NULL,"
        "  description TEXT,"
        "  problem TEXT,"
        "  target_group TEXT,"
        "  beneficiaries TEXT,"
        "  effectiveness TEXT,"
        "  authors TEXT,"
        "  summary TEXT NOT NULL,"
        "  summary_vector vector(1024),"
        "  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        ");"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS project_chunks ("
        "  id SERIAL PRIMARY KEY,"
        "  project_slug VARCHAR(255) REFERENCES projects(slug) ON DELETE CASCADE,"
        "  chunk_index INT NOT NULL,"
        "  source_file TEXT,"
        "  content TEXT NOT NULL,"
        "  content_vector vector(1024),"
        "  tsv tsvector GENERATED ALWAYS AS (to_tsvector('polish', content)) STORED,"
        "  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        ");"
    )

    rows = []
    projects_data = [
        (
            f"bawita_{token}",
            "BaWita",
            "Dla seniorów",
            "dla-seniorow",
            "https://rops.krakow.pl/innowacja/bawita",
            "Tablica sensoryczna dla seniorów z demencją.",
            "Otępienie u osób starszych.",
            "Seniorzy",
            "DPS",
            "Skuteczna",
            "Jan Kowalski",
            "Projekt BaWita to tablica manipulacyjna wspierająca pamięć i sprawność manualną.",
        ),
        (
            f"sciezka_{token}",
            "Ścieżka motosensoryczna",
            "Dla dzieci",
            "dla-dzieci",
            "https://rops.krakow.pl/innowacja/sciezka",
            "Ścieżka sensoryczna dla przedszkoli.",
            "Brak integracji sensorycznej.",
            "Dzieci przedszkolne",
            "Przedszkola",
            "Wysoka",
            "Anna Nowak",
            "Innowacja ścieżka motosensoryczna rozwija koordynację ruchową u dzieci.",
        ),
    ]

    for item in projects_data:
        row = connection.execute(
            "INSERT INTO projects ("
            "  slug, title, category, category_slug, url, description, problem, "
            "  target_group, beneficiaries, effectiveness, authors, summary"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
            item,
        ).fetchone()
        rows.append(row)

    # insert sample chunk
    connection.execute(
        "INSERT INTO project_chunks (project_slug, chunk_index, source_file, content) "
        "VALUES (%s, %s, %s, %s)",
        (
            f"bawita_{token}",
            0,
            "instrukcja.pdf",
            "Elementy drewnianej tablicy BaWita stymulują pamięć proceduralną seniora.",
        ),
    )

    return rows


def test_list_projects(client: TestClient, sample_projects):
    response = client.get("/projects")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2


def test_list_projects_filter_category(client: TestClient, sample_projects):
    response = client.get("/projects?category=Dla seniorów")
    assert response.status_code == 200
    data = response.json()
    assert all(item["category"] == "Dla seniorów" for item in data["items"])


def test_list_categories(client: TestClient, sample_projects):
    response = client.get("/projects/categories")
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) >= 2
    category_names = [c["category"] for c in categories]
    assert "Dla seniorów" in category_names
    assert "Dla dzieci" in category_names


def test_get_project_by_slug(client: TestClient, sample_projects):
    target = sample_projects[0]
    response = client.get(f"/projects/{target['slug']}")
    assert response.status_code == 200
    project = response.json()
    assert project["slug"] == target["slug"]
    assert project["title"] == target["title"]


def test_get_project_not_found(client: TestClient):
    response = client.get("/projects/non-existent-slug-123")
    assert response.status_code == 404


def test_search_projects_text(client: TestClient, sample_projects):
    response = client.post(
        "/projects/search",
        json={"query": "tablica manipulacyjna sensoryczna", "limit": 5},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    top = results[0]
    assert "BaWita" in top["title"]
    assert top["score"] > 0
