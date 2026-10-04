-- migrate:up
CREATE TABLE report_visualization_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX report_visualization_attempts_report_id_created_at_idx
    ON report_visualization_attempts (report_id, created_at);

-- migrate:down
DROP TABLE report_visualization_attempts;
