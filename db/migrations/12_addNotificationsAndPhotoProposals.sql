-- migrate:up
-- a photo offered for a case that has none. It stands on the map and in the
-- case's sheet under a question mark until the resident who filed the case
-- first either takes it or turns it down.
CREATE TABLE master_report_photo_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_report_id UUID NOT NULL REFERENCES master_reports(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- a persistent file or object-storage key, not an expiring download URL.
    storage_key TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    -- when the case's author took or turned down the photo, null while it waits.
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT master_report_photo_proposals_state_check
        CHECK (state IN ('pending', 'approved', 'rejected')),
    CONSTRAINT master_report_photo_proposals_storage_key_check CHECK (BTRIM(storage_key) <> ''),
    CONSTRAINT master_report_photo_proposals_decided_at_check
        CHECK ((state = 'pending') = (decided_at IS NULL))
);

CREATE INDEX master_report_photo_proposals_master_report_id_created_at_id_idx
    ON master_report_photo_proposals (master_report_id, created_at, id);
CREATE INDEX master_report_photo_proposals_user_id_idx ON master_report_photo_proposals (user_id);
-- at most one photo waits for a decision per case, so the question mark is never ambiguous.
CREATE UNIQUE INDEX master_report_photo_proposals_pending_idx
    ON master_report_photo_proposals (master_report_id) WHERE state = 'pending';

-- what the notifications page shows: one row per thing that happened to a case
-- the recipient filed, commented on, or offered a photo for.
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    master_report_id UUID REFERENCES master_reports(id) ON DELETE CASCADE,
    photo_proposal_id UUID REFERENCES master_report_photo_proposals(id) ON DELETE CASCADE,
    -- the case's title as it read when this happened, so the list still reads
    -- after the case was renamed.
    subject TEXT NOT NULL,
    -- what else to show under the title: a comment, an official response.
    detail TEXT,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT notifications_kind_check CHECK (kind IN (
        'status_inprogress', 'status_finished', 'comment', 'update',
        'photo_proposal', 'photo_approved', 'photo_rejected'
    )),
    CONSTRAINT notifications_subject_check CHECK (BTRIM(subject) <> '')
);

CREATE INDEX notifications_user_id_created_at_id_idx ON notifications (user_id, created_at DESC, id);
-- the navbar's unread count reads only the rows that have not been opened.
CREATE INDEX notifications_unread_idx ON notifications (user_id) WHERE read_at IS NULL;
CREATE INDEX notifications_master_report_id_idx ON notifications (master_report_id);
CREATE INDEX notifications_photo_proposal_id_idx ON notifications (photo_proposal_id);

-- migrate:down
DROP TABLE notifications;
DROP TABLE master_report_photo_proposals;
