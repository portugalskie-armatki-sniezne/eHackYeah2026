-- migrate:up
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'office', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE report_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- a shared response for reports about the same issue.
    response TEXT,
    edited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    report_group_id UUID REFERENCES report_groups(id) ON DELETE SET NULL,
    description TEXT NOT NULL CHECK (BTRIM(description) <> ''),
    -- coordinates in WGS 84: longitude first, latitude second. Distances are in meters.
    location GEOGRAPHY(POINT, 4326) NOT NULL CHECK (NOT ST_IsEmpty(location::geometry)),
    edited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX reports_user_id_idx ON reports (user_id);
CREATE INDEX reports_report_group_id_idx ON reports (report_group_id);
CREATE INDEX reports_location_idx ON reports USING GIST (location);

CREATE TABLE report_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    -- a persistent file or object-storage key, not an expiring download URL.
    storage_key TEXT NOT NULL CHECK (BTRIM(storage_key) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_id, storage_key)
);

CREATE FUNCTION set_edited_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.edited_at = statement_timestamp();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER reports_set_edited_at
BEFORE UPDATE ON reports
FOR EACH ROW EXECUTE FUNCTION set_edited_at();

CREATE TRIGGER report_groups_set_edited_at
BEFORE UPDATE ON report_groups
FOR EACH ROW EXECUTE FUNCTION set_edited_at();

-- migrate:down
DROP TABLE report_photos;
DROP TABLE reports;
DROP TABLE report_groups;
DROP TABLE users;
DROP FUNCTION set_edited_at();
