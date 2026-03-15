-- Repair history audit trail: log every status change on a case (who, when, old -> new).
-- case_id links to cases(id); changed_by links to staff(id) when set.
CREATE TABLE IF NOT EXISTS case_status_history (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT now(),
    changed_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_case_status_history_case_id ON case_status_history(case_id);
