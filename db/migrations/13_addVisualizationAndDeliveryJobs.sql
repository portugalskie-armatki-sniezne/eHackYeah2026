-- migrate:up
CREATE TABLE visualization_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_id UUID UNIQUE REFERENCES reports(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE visualization_jobs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    draft_id UUID REFERENCES visualization_drafts(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    description TEXT NOT NULL,
    source_keys JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    storage_key TEXT,
    prompt TEXT,
    media_type TEXT,
    error_code TEXT,
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, idempotency_key),
    CHECK (status <> 'succeeded' OR (storage_key IS NOT NULL AND completed_at IS NOT NULL))
);

CREATE UNIQUE INDEX visualization_jobs_active_user_idx ON visualization_jobs (user_id)
    WHERE status IN ('queued', 'running');
CREATE INDEX visualization_jobs_user_created_idx ON visualization_jobs (user_id, created_at);
CREATE INDEX visualization_jobs_draft_created_idx ON visualization_jobs (draft_id, created_at, id);
CREATE INDEX visualization_jobs_queue_idx ON visualization_jobs (created_at) WHERE status = 'queued';

CREATE TABLE mail_delivery_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    master_report_id UUID UNIQUE REFERENCES master_reports(id) ON DELETE SET NULL,
    visualization_job_id UUID REFERENCES visualization_jobs(id) ON DELETE SET NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'sent', 'failed', 'unknown')),
    mock BOOLEAN NOT NULL DEFAULT true CHECK (mock),
    error_code TEXT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dispatched_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX mail_delivery_jobs_user_dispatched_idx ON mail_delivery_jobs (user_id, dispatched_at);
CREATE INDEX mail_delivery_jobs_queue_idx ON mail_delivery_jobs (next_attempt_at, created_at)
    WHERE status = 'queued';

-- migrate:down
DROP TABLE mail_delivery_jobs;
DROP TABLE visualization_jobs;
DROP TABLE visualization_drafts;
