-- migrate:up
INSERT INTO report_categories (name) VALUES ('improvement'), ('issue');

INSERT INTO master_report_statuses (name) VALUES ('created'), ('reported'), ('inprogress'), ('finished');

-- migrate:down
DELETE FROM master_report_statuses WHERE name IN ('created', 'reported', 'inprogress', 'finished');

DELETE FROM report_categories WHERE name IN ('improvement', 'issue');
