-- migrate:up
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    edited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE report_categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE master_report_statuses (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE master_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_category_id BIGINT NOT NULL,
    status_id BIGINT NOT NULL,
    responsible_institution_id BIGINT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    -- a shared response for reports about the same issue.
    response TEXT,
    edited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX master_reports_report_category_id_idx ON master_reports (report_category_id);
CREATE INDEX master_reports_status_id_idx ON master_reports (status_id);
CREATE INDEX master_reports_responsible_institution_id_idx ON master_reports (responsible_institution_id);
CREATE INDEX master_reports_location_idx ON master_reports USING GIST (location);

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    master_report_id UUID,
    report_category_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    -- coordinates in WGS 84: longitude first, latitude second. Distances are in meters.
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    edited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX reports_user_id_idx ON reports (user_id);
CREATE INDEX reports_master_report_id_idx ON reports (master_report_id);
CREATE INDEX reports_report_category_id_idx ON reports (report_category_id);
CREATE INDEX reports_location_idx ON reports USING GIST (location);

CREATE TABLE report_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL,
    -- a persistent file or object-storage key, not an expiring download URL.
    storage_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE master_report_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_report_id UUID NOT NULL,
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX master_report_comments_master_report_id_created_at_id_idx ON master_report_comments (master_report_id, created_at, id);
CREATE INDEX master_report_comments_user_id_idx ON master_report_comments (user_id);

CREATE TABLE master_report_comment_likes (
    comment_id UUID NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (comment_id, user_id)
);

CREATE INDEX master_report_comment_likes_user_id_idx ON master_report_comment_likes (user_id);

CREATE FUNCTION set_edited_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.edited_at = statement_timestamp();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_set_edited_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_edited_at();

CREATE TRIGGER reports_set_edited_at
BEFORE UPDATE ON reports
FOR EACH ROW EXECUTE FUNCTION set_edited_at();

CREATE TRIGGER master_reports_set_edited_at
BEFORE UPDATE ON master_reports
FOR EACH ROW EXECUTE FUNCTION set_edited_at();

-- migrate:down
DROP TABLE master_report_comment_likes;
DROP TABLE master_report_comments;
DROP TABLE report_photos;
DROP TABLE reports;
DROP TABLE master_reports;
DROP TABLE master_report_statuses;
DROP TABLE report_categories;
DROP TABLE users;
DROP FUNCTION set_edited_at();
