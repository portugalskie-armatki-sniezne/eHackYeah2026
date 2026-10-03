BEGIN;

DO $$
DECLARE
    author_id UUID;
    master_id UUID;
    report_id UUID;
    comment_id UUID;
    category_id BIGINT;
    created_status_id BIGINT;
    institution_id BIGINT;
    service_entity_id BIGINT;
    contact RECORD;
BEGIN
    FOR contact IN SELECT * FROM (VALUES
        ('email@example.invalid'::TEXT, NULL::TEXT),
        (NULL, '+48123456789'),
        ('both@example.invalid', '+48987654321')
    ) AS contacts(email, phone) LOOP
        INSERT INTO users (first_name, last_name, email, phone, password_hash)
        VALUES ('Contact', 'Check', contact.email, contact.phone, 'test-only-placeholder');
    END LOOP;
    FOR contact IN SELECT * FROM (VALUES
        (NULL::TEXT, NULL::TEXT), ('', NULL), (NULL, ''), ('   ', '   ')
    ) AS contacts(email, phone) LOOP
        BEGIN
            INSERT INTO users (first_name, last_name, email, phone, password_hash)
            VALUES ('Invalid', 'Contact', contact.email, contact.phone, 'test-only-placeholder');
            RAISE EXCEPTION 'User without a nonblank contact accepted';
        EXCEPTION WHEN check_violation THEN NULL;
        END;
    END LOOP;
    BEGIN
        INSERT INTO users (first_name, last_name, email, password_hash)
        VALUES ('Duplicate', 'Email', 'email@example.invalid', 'test-only-placeholder');
        RAISE EXCEPTION 'Duplicate email accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    INSERT INTO users (first_name, last_name, phone, password_hash)
    VALUES ('Another', 'Phone', '+48111222333', 'test-only-placeholder')
    RETURNING id INTO author_id;
    BEGIN
        UPDATE users SET phone = NULL WHERE id = author_id;
        RAISE EXCEPTION 'Removing the last user contact accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    SELECT id INTO category_id FROM report_categories WHERE name = 'improvement';
    BEGIN
        INSERT INTO report_categories (name) VALUES ('improvement');
        RAISE EXCEPTION 'Duplicate report category accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO report_categories (name) VALUES ('   ');
        RAISE EXCEPTION 'Blank report category accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    SELECT id INTO created_status_id FROM master_report_statuses WHERE name = 'created';
    BEGIN
        INSERT INTO master_report_statuses (name) VALUES ('created');
        RAISE EXCEPTION 'Duplicate master report status accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO master_report_statuses (name) VALUES ('   ');
        RAISE EXCEPTION 'Blank master report status accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    INSERT INTO master_reports (report_category_id, status_id, title, description, location)
    VALUES (category_id, created_status_id, 'More benches', 'Add benches near the park',
            'SRID=4326;POINT(19.94 50.06)')
    RETURNING id INTO master_id;
    BEGIN
        UPDATE master_reports SET title = '   ' WHERE id = master_id;
        RAISE EXCEPTION 'Blank master report title accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET title = NULL WHERE id = master_id;
        RAISE EXCEPTION 'Missing master report title accepted';
    EXCEPTION WHEN not_null_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET description = '   ' WHERE id = master_id;
        RAISE EXCEPTION 'Blank master report description accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET location = 'SRID=4326;POINT EMPTY' WHERE id = master_id;
        RAISE EXCEPTION 'Empty master report location accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET report_category_id = 0 WHERE id = master_id;
        RAISE EXCEPTION 'Unknown master report category accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET report_category_id = NULL WHERE id = master_id;
        RAISE EXCEPTION 'Missing master report category accepted';
    EXCEPTION WHEN not_null_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET status_id = 0 WHERE id = master_id;
        RAISE EXCEPTION 'Unknown master report status accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET status_id = NULL WHERE id = master_id;
        RAISE EXCEPTION 'Missing master report status accepted';
    EXCEPTION WHEN not_null_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET responsible_office_id = 0 WHERE id = master_id;
        RAISE EXCEPTION 'Unknown responsible institution accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        DELETE FROM master_report_statuses WHERE id = created_status_id;
        RAISE EXCEPTION 'Referenced master report status could be deleted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    SELECT id INTO institution_id FROM local_government_offices ORDER BY id LIMIT 1;
    UPDATE master_reports SET responsible_office_id = institution_id WHERE id = master_id;
    BEGIN
        DELETE FROM local_government_offices WHERE id = institution_id;
        RAISE EXCEPTION 'Responsible institution could be deleted while referenced';
    EXCEPTION WHEN restrict_violation THEN NULL;
    END;

    SELECT id INTO service_entity_id FROM service_entities ORDER BY id LIMIT 1;
    BEGIN
        UPDATE master_reports SET responsible_service_entity_id = service_entity_id WHERE id = master_id;
        RAISE EXCEPTION 'Two responsible parties accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_reports SET responsible_office_id = NULL, responsible_service_entity_id = 0
        WHERE id = master_id;
        RAISE EXCEPTION 'Unknown responsible service entity accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    UPDATE master_reports
    SET responsible_office_id = NULL, responsible_service_entity_id = service_entity_id
    WHERE id = master_id;
    IF (SELECT responsible_service_entity_id FROM master_reports WHERE id = master_id)
       IS DISTINCT FROM service_entity_id THEN
        RAISE EXCEPTION 'Service entity assignment was not saved';
    END IF;
    BEGIN
        DELETE FROM service_entities WHERE id = service_entity_id;
        RAISE EXCEPTION 'Responsible service entity could be deleted while referenced';
    EXCEPTION WHEN restrict_violation THEN NULL;
    END;
    UPDATE master_reports SET responsible_service_entity_id = NULL WHERE id = master_id;
    IF EXISTS (SELECT FROM master_reports WHERE id = master_id
               AND (responsible_office_id IS NOT NULL OR responsible_service_entity_id IS NOT NULL)) THEN
        RAISE EXCEPTION 'Responsible party could not be unassigned';
    END IF;

    INSERT INTO reports (user_id, master_report_id, report_category_id, title, description, location)
    VALUES (author_id, master_id, category_id, 'More benches', 'Add benches near the park',
            'SRID=4326;POINT(19.94 50.06)')
    RETURNING id INTO report_id;
    BEGIN
        UPDATE reports SET title = '   ' WHERE id = report_id;
        RAISE EXCEPTION 'Blank report title accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE reports SET title = NULL WHERE id = report_id;
        RAISE EXCEPTION 'Missing report title accepted';
    EXCEPTION WHEN not_null_violation THEN NULL;
    END;
    BEGIN
        UPDATE reports SET description = '   ' WHERE id = report_id;
        RAISE EXCEPTION 'Blank report description accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE reports SET user_id = gen_random_uuid() WHERE id = report_id;
        RAISE EXCEPTION 'Unknown report author accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE reports SET master_report_id = gen_random_uuid() WHERE id = report_id;
        RAISE EXCEPTION 'Unknown master report accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    UPDATE reports SET master_report_id = NULL WHERE id = report_id;
    IF (SELECT master_report_id FROM reports WHERE id = report_id) IS NOT NULL THEN
        RAISE EXCEPTION 'Report could not remain unclassified without a master';
    END IF;
    UPDATE reports SET master_report_id = master_id WHERE id = report_id;
    BEGIN
        UPDATE reports SET report_category_id = 0 WHERE id = report_id;
        RAISE EXCEPTION 'Unknown report category accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE reports SET report_category_id = NULL WHERE id = report_id;
        RAISE EXCEPTION 'Missing report category accepted';
    EXCEPTION WHEN not_null_violation THEN NULL;
    END;
    BEGIN
        DELETE FROM report_categories WHERE id = category_id;
        RAISE EXCEPTION 'Referenced report category could be deleted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO report_photos (report_id, storage_key) VALUES (report_id, '   ');
        RAISE EXCEPTION 'Blank photo storage key accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO report_photos (report_id, storage_key) VALUES (gen_random_uuid(), 'reports/missing.jpg');
        RAISE EXCEPTION 'Photo without a report accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    INSERT INTO master_report_comments (master_report_id, user_id, content)
    VALUES (master_id, author_id, 'A bench would help') RETURNING id INTO comment_id;
    BEGIN
        UPDATE master_report_comments SET content = '   ' WHERE id = comment_id;
        RAISE EXCEPTION 'Blank comment accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_report_comments SET master_report_id = gen_random_uuid() WHERE id = comment_id;
        RAISE EXCEPTION 'Comment without a master report accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE master_report_comments SET user_id = gen_random_uuid() WHERE id = comment_id;
        RAISE EXCEPTION 'Comment without an author accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO master_report_comment_likes (comment_id, user_id) VALUES (gen_random_uuid(), author_id);
        RAISE EXCEPTION 'Like without a comment accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO master_report_comment_likes (comment_id, user_id) VALUES (comment_id, gen_random_uuid());
        RAISE EXCEPTION 'Like without a user accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO local_government_offices (teryt_code, local_government_name) VALUES ('invalid', 'Test');
        RAISE EXCEPTION 'Invalid TERYT code accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO local_government_offices (teryt_code, local_government_name) VALUES ('9999999', '   ');
        RAISE EXCEPTION 'Blank local government name accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO local_government_offices (teryt_code, local_government_name)
        SELECT teryt_code, local_government_name FROM local_government_offices LIMIT 1;
        RAISE EXCEPTION 'Duplicate TERYT code accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
END;
$$;

ROLLBACK;
