-- migrate:up
ALTER TABLE service_entities ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- migrate:down
ALTER TABLE service_entities DROP COLUMN is_active;
