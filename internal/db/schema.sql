-- Schema for Jules Orchestrator

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mission TEXT,           -- Detailed task description for LLM
    pattern TEXT,           -- Workflow pattern (discovery, story_writer, etc.)
    schedule TEXT NOT NULL, -- Cron format
    status TEXT NOT NULL,   -- PENDING, RUNNING, PAUSED, COMPLETED, FAILED
    last_run_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    input_data TEXT,        -- Request payload / prompt
    output_data TEXT,       -- Response payload / result
    status TEXT,            -- SUCCESS, FAILED
    error TEXT,             -- Error message if failed
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
    jules_session_id TEXT UNIQUE,
    status TEXT NOT NULL,
    last_context_hash TEXT, -- To detect new questions/blocks
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    action TEXT, -- e.g., "AUTO_RESPONDED", "ROUTED_TO_CLAUDE"
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_task_id ON sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON task_logs(task_id);
