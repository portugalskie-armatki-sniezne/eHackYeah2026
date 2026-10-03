-- migrate:up
ALTER TABLE users
    ALTER COLUMN password_hash DROP NOT NULL,
    ADD COLUMN google_sub TEXT,
    ADD CONSTRAINT users_google_sub_key UNIQUE (google_sub),
    ADD CONSTRAINT users_sign_in_check CHECK (password_hash IS NOT NULL OR google_sub IS NOT NULL);

-- migrate:down
-- accounts without a password get a value that no password matches.
UPDATE users SET password_hash = '!' WHERE password_hash IS NULL;

ALTER TABLE users
    DROP CONSTRAINT users_sign_in_check,
    DROP CONSTRAINT users_google_sub_key,
    DROP COLUMN google_sub,
    ALTER COLUMN password_hash SET NOT NULL;
