CREATE TABLE IF NOT EXISTS pending_actions (
    action_id  TEXT PRIMARY KEY,
    type       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Tracks Gmail message IDs that have already been acted on (sent/confirmed).
-- Used for idempotency: prevents re-processing the same email twice when the
-- same trigger fires more than once (Phase 5 / Phase 6).
CREATE TABLE IF NOT EXISTS processed_messages (
    message_id   TEXT NOT NULL,
    action_type  TEXT NOT NULL,
    action_id    TEXT NOT NULL REFERENCES pending_actions(action_id),
    processed_at TEXT NOT NULL,
    PRIMARY KEY (message_id, action_type)
);
