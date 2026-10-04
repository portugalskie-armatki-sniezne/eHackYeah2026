-- migrate:up
-- the social innovation library of ROPS Kraków, imported from db/seeds/rops_projects.json.
-- the chunk index below needs a 'polish' text search configuration; the PostGIS image
-- ships none, so a copy of the simple one stands in for it.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'polish') THEN
        CREATE TEXT SEARCH CONFIGURATION polish (COPY = simple);
    END IF;
END $$;

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    category_slug VARCHAR(255),
    url TEXT NOT NULL,
    description TEXT,
    problem TEXT,
    target_group TEXT,
    beneficiaries TEXT,
    effectiveness TEXT,
    authors TEXT,
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- the sections of an innovation page, one row each, searched for the matched snippet.
CREATE TABLE project_chunks (
    id SERIAL PRIMARY KEY,
    project_slug VARCHAR(255) NOT NULL REFERENCES projects(slug) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    source_file TEXT,
    content TEXT NOT NULL,
    tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('polish', content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX project_chunks_project_slug_idx ON project_chunks (project_slug);
CREATE INDEX project_chunks_tsv_idx ON project_chunks USING GIN (tsv);

-- the embedding columns need pgvector, which only some database images ship.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        CREATE EXTENSION IF NOT EXISTS vector;
        EXECUTE 'ALTER TABLE projects ADD COLUMN summary_vector vector(1024)';
        EXECUTE 'ALTER TABLE project_chunks ADD COLUMN content_vector vector(1024)';
    END IF;
END $$;

-- migrate:down
DROP TABLE project_chunks;
DROP TABLE projects;
DROP TEXT SEARCH CONFIGURATION IF EXISTS polish;
