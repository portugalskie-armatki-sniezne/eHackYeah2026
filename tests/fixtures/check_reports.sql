BEGIN;

DO $$
DECLARE
    author_id UUID;
    supporter_id UUID;
    master_id UUID;
    other_master_id UUID;
    first_report_id UUID;
    second_report_id UUID;
    first_comment_id UUID;
    second_comment_id UUID;
    other_comment_id UUID;
    issue_category_id BIGINT;
    created_status_id BIGINT;
    finished_status_id BIGINT;
    institution_id BIGINT;
    initial_time TIMESTAMPTZ := '2000-01-01 00:00:00+00';
BEGIN
    SELECT id INTO issue_category_id FROM report_categories WHERE name = 'issue';
    IF issue_category_id IS NULL
       OR (SELECT COUNT(*) FROM report_categories WHERE name IN ('improvement', 'issue')) <> 2 THEN
        RAISE EXCEPTION 'Initial report categories were not populated';
    END IF;

    SELECT id INTO created_status_id FROM master_report_statuses WHERE name = 'created';
    SELECT id INTO finished_status_id FROM master_report_statuses WHERE name = 'finished';
    IF (SELECT array_agg(name ORDER BY name) FROM master_report_statuses)
       IS DISTINCT FROM ARRAY['created', 'finished', 'inprogress', 'reported'] THEN
        RAISE EXCEPTION 'Initial master report statuses were not populated';
    END IF;
    SELECT id INTO institution_id FROM local_government_offices ORDER BY id LIMIT 1;

    INSERT INTO users (first_name, last_name, email, password_hash)
    VALUES ('Schema', 'Check', 'schema@example.invalid', 'test-only-placeholder')
    RETURNING id INTO author_id;
    INSERT INTO users (first_name, last_name, phone, password_hash)
    VALUES ('Comment', 'Supporter', '+48123456789', 'test-only-placeholder')
    RETURNING id INTO supporter_id;

    INSERT INTO reports (user_id, report_category_id, title, description, location, edited_at)
    VALUES (author_id, issue_category_id, 'Pavement repair', 'Broken pavement',
            'SRID=4326;POINT(19.94 50.06)', initial_time)
    RETURNING id INTO first_report_id;
    IF (SELECT master_report_id FROM reports WHERE id = first_report_id) IS NOT NULL
       OR EXISTS (SELECT FROM master_reports) THEN
        RAISE EXCEPTION 'Saving a report before classification created or required a master';
    END IF;

    INSERT INTO master_reports (report_category_id, status_id, title, description, location, response, edited_at)
    SELECT report_category_id, created_status_id, title, description, location, 'Repair scheduled', initial_time
    FROM reports WHERE id = first_report_id
    RETURNING id INTO master_id;
    UPDATE reports SET master_report_id = master_id WHERE id = first_report_id;
    INSERT INTO master_reports (report_category_id, status_id, title, description, location)
    VALUES (issue_category_id, created_status_id, 'Lamp repair', 'Broken lamp', 'SRID=4326;POINT(19.95 50.06)')
    RETURNING id INTO other_master_id;

    IF EXISTS (SELECT FROM master_reports WHERE id = master_id
               AND (responsible_office_id IS NOT NULL OR responsible_service_entity_id IS NOT NULL)) THEN
        RAISE EXCEPTION 'Master report required an institution before classification';
    END IF;

    INSERT INTO reports (user_id, report_category_id, title, description, location)
    VALUES (author_id, issue_category_id, 'More pavement damage', 'Another view',
            'SRID=4326;POINT(19.9401 50.06)')
    RETURNING id INTO second_report_id;
    UPDATE reports SET master_report_id = master_id WHERE id = second_report_id;

    IF (SELECT COUNT(*) FROM reports WHERE master_report_id = master_id) <> 2 THEN
        RAISE EXCEPTION 'Reports were not linked to their master';
    END IF;
    IF (SELECT m.response FROM reports r JOIN master_reports m ON m.id = r.master_report_id
        WHERE r.id = first_report_id) <> 'Repair scheduled' THEN
        RAISE EXCEPTION 'Shared response was not available';
    END IF;
    IF NOT (SELECT ST_DWithin(a.location, b.location, 20) FROM reports a, reports b
            WHERE a.id = first_report_id AND b.id = second_report_id) THEN
        RAISE EXCEPTION 'Geographic distance query failed';
    END IF;

    INSERT INTO report_photos (report_id, storage_key)
    VALUES (first_report_id, 'reports/one.jpg'), (first_report_id, 'reports/two.jpg'),
           (second_report_id, 'reports/three.jpg');

    INSERT INTO master_report_comments (master_report_id, user_id, content, created_at)
    VALUES (master_id, author_id, 'Still needs repair', initial_time + INTERVAL '1 second')
    RETURNING id INTO second_comment_id;
    INSERT INTO master_report_comments (master_report_id, user_id, content, created_at)
    VALUES (master_id, author_id, 'Reported today', initial_time)
    RETURNING id INTO first_comment_id;
    INSERT INTO master_report_comments (master_report_id, user_id, content)
    VALUES (other_master_id, author_id, 'Another master report comment')
    RETURNING id INTO other_comment_id;
    IF (SELECT array_agg(id ORDER BY created_at, id) FROM master_report_comments WHERE master_report_id = master_id)
       IS DISTINCT FROM ARRAY[first_comment_id, second_comment_id] THEN
        RAISE EXCEPTION 'Comments were not returned in master report context and chronological order';
    END IF;
    IF (SELECT COUNT(*) FROM reports r JOIN master_report_comments c ON c.master_report_id = r.master_report_id
        WHERE r.id = second_report_id) <> 2 THEN
        RAISE EXCEPTION 'Reports linked to the same master did not share comments';
    END IF;

    INSERT INTO master_report_comment_likes (comment_id, user_id)
    VALUES (first_comment_id, author_id), (first_comment_id, supporter_id), (other_comment_id, author_id);
    BEGIN
        INSERT INTO master_report_comment_likes (comment_id, user_id) VALUES (first_comment_id, author_id);
        RAISE EXCEPTION 'Duplicate comment like accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    IF (SELECT COUNT(*) FROM master_report_comment_likes WHERE comment_id = first_comment_id) <> 2 THEN
        RAISE EXCEPTION 'Comment likes were not counted correctly';
    END IF;
    DELETE FROM users WHERE id = supporter_id;
    IF (SELECT COUNT(*) FROM master_report_comment_likes WHERE comment_id = first_comment_id) <> 1 THEN
        RAISE EXCEPTION 'Deleting a user affected another user''s comment like';
    END IF;
    DELETE FROM master_report_comment_likes WHERE comment_id = first_comment_id AND user_id = author_id;
    INSERT INTO master_report_comment_likes (comment_id, user_id) VALUES (first_comment_id, author_id);

    BEGIN
        INSERT INTO report_photos (report_id, storage_key) VALUES (first_report_id, 'reports/one.jpg');
        RAISE EXCEPTION 'Duplicate photo reference accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO reports (user_id, master_report_id, report_category_id, title, description, location)
        VALUES (author_id, master_id, issue_category_id, 'Invalid location', 'Empty location', 'SRID=4326;POINT EMPTY');
        RAISE EXCEPTION 'Empty report location accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        DELETE FROM users WHERE id = author_id;
        RAISE EXCEPTION 'Report author could be deleted without handling reports';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    UPDATE reports SET description = 'Updated description' WHERE id = first_report_id;
    IF (SELECT description FROM master_reports WHERE id = master_id) <> 'Broken pavement' THEN
        RAISE EXCEPTION 'Editing an individual report changed the master description';
    END IF;
    UPDATE master_reports
    SET title = 'Shared pavement repair', description = 'Damage confirmed by multiple reports',
        responsible_office_id = institution_id,
        status_id = (SELECT id FROM master_report_statuses WHERE name = 'reported')
    WHERE id = master_id;
    UPDATE master_reports
    SET status_id = (SELECT id FROM master_report_statuses WHERE name = 'inprogress')
    WHERE id = master_id;
    UPDATE master_reports SET response = 'Repair completed', status_id = finished_status_id WHERE id = master_id;
    IF (SELECT title FROM reports WHERE id = first_report_id) <> 'Pavement repair'
       OR (SELECT description FROM reports WHERE id = first_report_id) <> 'Updated description'
       OR (SELECT description FROM reports WHERE id = second_report_id) <> 'Another view' THEN
        RAISE EXCEPTION 'Editing the master changed individual report content';
    END IF;
    IF (SELECT COUNT(*) FROM reports r JOIN master_reports m ON m.id = r.master_report_id
        WHERE r.id IN (first_report_id, second_report_id)
        AND m.status_id = finished_status_id AND m.responsible_office_id = institution_id) <> 2 THEN
        RAISE EXCEPTION 'Reports did not share their master status and institution';
    END IF;
    IF (SELECT edited_at FROM reports WHERE id = first_report_id) <= initial_time
       OR (SELECT edited_at FROM master_reports WHERE id = master_id) <= initial_time THEN
        RAISE EXCEPTION 'Edit timestamp was not updated';
    END IF;

    BEGIN
        DELETE FROM master_reports WHERE id = master_id;
        RAISE EXCEPTION 'Master report with linked reports could be deleted';
    EXCEPTION WHEN restrict_violation THEN NULL;
    END;
    DELETE FROM reports WHERE id = first_report_id;
    IF EXISTS (SELECT FROM report_photos WHERE report_id = first_report_id)
       OR (SELECT COUNT(*) FROM report_photos WHERE report_id = second_report_id) <> 1 THEN
        RAISE EXCEPTION 'Photo cascade affected the wrong reports';
    END IF;
    IF NOT EXISTS (SELECT FROM master_reports WHERE id = master_id)
       OR (SELECT COUNT(*) FROM master_report_comments WHERE master_report_id = master_id) <> 2
       OR (SELECT COUNT(*) FROM master_report_comment_likes WHERE comment_id = first_comment_id) <> 1 THEN
        RAISE EXCEPTION 'Deleting an individual report affected its master, comments, or likes';
    END IF;

    DELETE FROM reports WHERE id = second_report_id;
    IF NOT EXISTS (SELECT FROM master_reports WHERE id = master_id)
       OR (SELECT COUNT(*) FROM master_report_comments WHERE master_report_id = master_id) <> 2 THEN
        RAISE EXCEPTION 'Deleting the last individual report removed the shared master or comments';
    END IF;
    DELETE FROM master_reports WHERE id = master_id;
    IF EXISTS (SELECT FROM master_report_comments WHERE master_report_id = master_id)
       OR EXISTS (SELECT FROM master_report_comment_likes WHERE comment_id = first_comment_id)
       OR (SELECT COUNT(*) FROM master_report_comments WHERE master_report_id = other_master_id) <> 1
       OR (SELECT COUNT(*) FROM master_report_comment_likes WHERE comment_id = other_comment_id) <> 1 THEN
        RAISE EXCEPTION 'Comment and like cascade affected the wrong master reports';
    END IF;
END;
$$;

ROLLBACK;
