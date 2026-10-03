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
    ADD CONSTRAINT master_reports_responsible_office_id_fkey
        FOREIGN KEY (responsible_office_id) REFERENCES local_government_offices(id) ON DELETE RESTRICT,
    ADD CONSTRAINT master_reports_responsible_service_entity_id_fkey
        FOREIGN KEY (responsible_service_entity_id) REFERENCES service_entities(id) ON DELETE RESTRICT,
    ADD CONSTRAINT master_reports_responsible_party_check CHECK (
        num_nonnulls(responsible_office_id, responsible_service_entity_id) <= 1
    ),
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

ALTER TABLE local_government_offices
    ADD CONSTRAINT local_government_offices_teryt_code_key UNIQUE (teryt_code),
    ADD CONSTRAINT local_government_offices_teryt_code_check CHECK (teryt_code ~ '^[0-9]{7}$'),
    ADD CONSTRAINT local_government_offices_local_government_name_check CHECK (BTRIM(local_government_name) <> '');

ALTER TABLE service_entities
    ADD CONSTRAINT service_entities_source_key_key UNIQUE (source_key),
    ADD CONSTRAINT service_entities_source_key_check CHECK (BTRIM(source_key) <> ''),
    ADD CONSTRAINT service_entities_name_check CHECK (BTRIM(name) <> ''),
    ADD CONSTRAINT service_entities_entity_type_check CHECK (entity_type IN (
        'road_manager', 'transport_authority', 'transport_operator', 'green_space_manager',
        'water_infrastructure_manager', 'water_sewage_utility', 'water_sewage_authority', 'heating_utility',
        'waste_management', 'municipal_services', 'municipal_guard', 'housing_manager',
        'cemetery_manager', 'sports_infrastructure_manager', 'municipal_investment'
    )),
    ADD CONSTRAINT service_entities_teryt_code_check CHECK (teryt_code ~ '^[0-9]{7}$'),
    ADD CONSTRAINT service_entities_sources_check CHECK (
        cardinality(source_urls) > 0 AND array_position(source_urls, NULL) IS NULL
    );

-- migrate:down
ALTER TABLE service_entities
    DROP CONSTRAINT service_entities_sources_check,
    DROP CONSTRAINT service_entities_teryt_code_check,
    DROP CONSTRAINT service_entities_entity_type_check,
    DROP CONSTRAINT service_entities_name_check,
    DROP CONSTRAINT service_entities_source_key_check,
    DROP CONSTRAINT service_entities_source_key_key;

ALTER TABLE local_government_offices
    DROP CONSTRAINT local_government_offices_local_government_name_check,
    DROP CONSTRAINT local_government_offices_teryt_code_check,
    DROP CONSTRAINT local_government_offices_teryt_code_key;

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
    DROP CONSTRAINT master_reports_responsible_party_check,
    DROP CONSTRAINT master_reports_responsible_service_entity_id_fkey,
    DROP CONSTRAINT master_reports_responsible_office_id_fkey,
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
