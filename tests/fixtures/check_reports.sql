BEGIN;

DO $$
DECLARE
    author_id UUID;
    group_id UUID;
    first_report_id UUID;
    second_report_id UUID;
    initial_time TIMESTAMPTZ := '2000-01-01 00:00:00+00';
BEGIN
    INSERT INTO users (first_name, last_name, email, password_hash)
    VALUES ('Schema', 'Check', 'schema@example.invalid', 'test-only-placeholder')
    RETURNING id INTO author_id;

    INSERT INTO report_groups (response, edited_at)
    VALUES ('Repair scheduled', initial_time) RETURNING id INTO group_id;

    INSERT INTO reports (user_id, report_group_id, description, location, edited_at)
    VALUES (author_id, group_id, 'Broken pavement', 'SRID=4326;POINT(19.94 50.06)', initial_time)
    RETURNING id INTO first_report_id;

    INSERT INTO reports (user_id, report_group_id, description, location)
    VALUES (author_id, group_id, 'Another view', 'SRID=4326;POINT(19.9401 50.06)')
    RETURNING id INTO second_report_id;

    IF (SELECT COUNT(*) FROM reports WHERE report_group_id = group_id) <> 2 THEN
        RAISE EXCEPTION 'Reports were not grouped';
    END IF;
    IF (SELECT g.response FROM reports r JOIN report_groups g ON g.id = r.report_group_id
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
    BEGIN
        INSERT INTO report_photos (report_id, storage_key) VALUES (first_report_id, 'reports/one.jpg');
        RAISE EXCEPTION 'Duplicate photo reference accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO reports (user_id, description, location)
        VALUES (author_id, 'Empty location', 'SRID=4326;POINT EMPTY');
        RAISE EXCEPTION 'Empty report location accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        DELETE FROM users WHERE id = author_id;
        RAISE EXCEPTION 'Report author could be deleted without handling reports';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    UPDATE reports SET description = 'Updated description' WHERE id = first_report_id;
    UPDATE report_groups SET response = 'Repair completed' WHERE id = group_id;
    IF (SELECT edited_at FROM reports WHERE id = first_report_id) <= initial_time
       OR (SELECT edited_at FROM report_groups WHERE id = group_id) <= initial_time THEN
        RAISE EXCEPTION 'Edit timestamp was not updated';
    END IF;

    DELETE FROM report_groups WHERE id = group_id;
    IF (SELECT COUNT(*) FROM reports WHERE id IN (first_report_id, second_report_id)
        AND report_group_id IS NULL) <> 2 THEN
        RAISE EXCEPTION 'Deleting a group did not preserve its reports';
    END IF;
    DELETE FROM reports WHERE id = first_report_id;
    IF EXISTS (SELECT FROM report_photos WHERE report_id = first_report_id)
       OR (SELECT COUNT(*) FROM report_photos WHERE report_id = second_report_id) <> 1 THEN
        RAISE EXCEPTION 'Photo cascade affected the wrong reports';
    END IF;
END;
$$;

ROLLBACK;
