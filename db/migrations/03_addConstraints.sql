-- migrate:up
ALTER TABLE users
    ADD CONSTRAINT users_email_key UNIQUE (email),
    ADD CONSTRAINT users_phone_key UNIQUE (phone),
    ADD CONSTRAINT users_contact_check CHECK (
        NULLIF(BTRIM(email), '') IS NOT NULL OR NULLIF(BTRIM(phone), '') IS NOT NULL
    ),
    ADD CONSTRAINT users_role_check CHECK (role IN ('user', 'office', 'admin'));

ALTER TABLE report_categories
    ADD CONSTRAINT report_categories_name_key UNIQUE (name),
    ADD CONSTRAINT report_categories_name_check CHECK (BTRIM(name) <> '');

ALTER TABLE master_report_statuses
    ADD CONSTRAINT master_report_statuses_name_key UNIQUE (name),
    ADD CONSTRAINT master_report_statuses_name_check CHECK (BTRIM(name) <> '');

ALTER TABLE master_reports
    ADD CONSTRAINT master_reports_report_category_id_fkey
        FOREIGN KEY (report_category_id) REFERENCES report_categories(id),
    ADD CONSTRAINT master_reports_status_id_fkey
        FOREIGN KEY (status_id) REFERENCES master_report_statuses(id),
    ADD CONSTRAINT master_reports_responsible_institution_id_fkey
        FOREIGN KEY (responsible_institution_id) REFERENCES institution_contacts(id),
    ADD CONSTRAINT master_reports_title_check CHECK (BTRIM(title) <> ''),
    ADD CONSTRAINT master_reports_description_check CHECK (BTRIM(description) <> ''),
    ADD CONSTRAINT master_reports_location_check CHECK (NOT ST_IsEmpty(location::geometry));

ALTER TABLE reports
    ADD CONSTRAINT reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id),
    ADD CONSTRAINT reports_master_report_id_fkey
        FOREIGN KEY (master_report_id) REFERENCES master_reports(id) ON DELETE RESTRICT,
    ADD CONSTRAINT reports_report_category_id_fkey
        FOREIGN KEY (report_category_id) REFERENCES report_categories(id),
    ADD CONSTRAINT reports_title_check CHECK (BTRIM(title) <> ''),
    ADD CONSTRAINT reports_description_check CHECK (BTRIM(description) <> ''),
    ADD CONSTRAINT reports_location_check CHECK (NOT ST_IsEmpty(location::geometry));

ALTER TABLE report_photos
    ADD CONSTRAINT report_photos_report_id_fkey
        FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
    ADD CONSTRAINT report_photos_storage_key_check CHECK (BTRIM(storage_key) <> ''),
    ADD CONSTRAINT report_photos_report_id_storage_key_key UNIQUE (report_id, storage_key);

ALTER TABLE master_report_comments
    ADD CONSTRAINT master_report_comments_master_report_id_fkey
        FOREIGN KEY (master_report_id) REFERENCES master_reports(id) ON DELETE CASCADE,
    ADD CONSTRAINT master_report_comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id),
    ADD CONSTRAINT master_report_comments_content_check CHECK (BTRIM(content) <> '');

ALTER TABLE master_report_comment_likes
    ADD CONSTRAINT master_report_comment_likes_comment_id_fkey
        FOREIGN KEY (comment_id) REFERENCES master_report_comments(id) ON DELETE CASCADE,
    ADD CONSTRAINT master_report_comment_likes_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE institution_contacts
    ADD CONSTRAINT institution_contacts_teryt_code_key UNIQUE (teryt_code),
    ADD CONSTRAINT institution_contacts_teryt_code_check CHECK (teryt_code ~ '^[0-9]{7}$'),
    ADD CONSTRAINT institution_contacts_local_government_name_check CHECK (BTRIM(local_government_name) <> '');

-- migrate:down
ALTER TABLE institution_contacts
    DROP CONSTRAINT institution_contacts_local_government_name_check,
    DROP CONSTRAINT institution_contacts_teryt_code_check,
    DROP CONSTRAINT institution_contacts_teryt_code_key;

ALTER TABLE master_report_comment_likes
    DROP CONSTRAINT master_report_comment_likes_user_id_fkey,
    DROP CONSTRAINT master_report_comment_likes_comment_id_fkey;

ALTER TABLE master_report_comments
    DROP CONSTRAINT master_report_comments_content_check,
    DROP CONSTRAINT master_report_comments_user_id_fkey,
    DROP CONSTRAINT master_report_comments_master_report_id_fkey;

ALTER TABLE report_photos
    DROP CONSTRAINT report_photos_report_id_storage_key_key,
    DROP CONSTRAINT report_photos_storage_key_check,
    DROP CONSTRAINT report_photos_report_id_fkey;

ALTER TABLE reports
    DROP CONSTRAINT reports_location_check,
    DROP CONSTRAINT reports_description_check,
    DROP CONSTRAINT reports_title_check,
    DROP CONSTRAINT reports_report_category_id_fkey,
    DROP CONSTRAINT reports_master_report_id_fkey,
    DROP CONSTRAINT reports_user_id_fkey;

ALTER TABLE master_reports
    DROP CONSTRAINT master_reports_location_check,
    DROP CONSTRAINT master_reports_description_check,
    DROP CONSTRAINT master_reports_title_check,
    DROP CONSTRAINT master_reports_responsible_institution_id_fkey,
    DROP CONSTRAINT master_reports_status_id_fkey,
    DROP CONSTRAINT master_reports_report_category_id_fkey;

ALTER TABLE master_report_statuses
    DROP CONSTRAINT master_report_statuses_name_check,
    DROP CONSTRAINT master_report_statuses_name_key;

ALTER TABLE report_categories
    DROP CONSTRAINT report_categories_name_check,
    DROP CONSTRAINT report_categories_name_key;

ALTER TABLE users
    DROP CONSTRAINT users_role_check,
    DROP CONSTRAINT users_contact_check,
    DROP CONSTRAINT users_phone_key,
    DROP CONSTRAINT users_email_key;
