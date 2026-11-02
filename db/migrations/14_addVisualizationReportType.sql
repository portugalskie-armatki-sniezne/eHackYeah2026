-- migrate:up
-- what the picture shows: an improvement carried out, or a reported issue repaired.
ALTER TABLE visualization_jobs
    ADD COLUMN report_type TEXT NOT NULL DEFAULT 'improvement'
    CHECK (report_type IN ('improvement', 'issue'));

-- migrate:down
ALTER TABLE visualization_jobs DROP COLUMN report_type;
