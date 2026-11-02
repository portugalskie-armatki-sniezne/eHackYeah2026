-- migrate:up
-- an office or admin comment that stands out under the master's discussion.
ALTER TABLE master_report_comments ADD COLUMN highlighted BOOLEAN NOT NULL DEFAULT FALSE;

-- migrate:down
ALTER TABLE master_report_comments DROP COLUMN highlighted;
