-- Schema for Jules Orchestrator

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,       -- Repository name (e.g. org/repo)
    agent TEXT DEFAULT '',    -- Agent persona (e.g. analyst, orchestrator)
    mission TEXT,             -- Short label shown in UI
    pattern TEXT,             -- Workflow pattern (discovery, story_writer, etc.)
    schedule TEXT NOT NULL,   -- Cron format
    status TEXT NOT NULL,     -- PENDING, RUNNING, PAUSED, COMPLETED, FAILED
    current_stage TEXT DEFAULT 'idle', -- analysis, planning, implementation, verification
    progress INTEGER DEFAULT 0,
    last_run_at DATETIME,
    approval_required INTEGER DEFAULT 0,
    pending_decision TEXT DEFAULT '',
    failure_count INTEGER DEFAULT 0,
    importance INTEGER DEFAULT 1,
    category TEXT DEFAULT 'worker',
    auto_paused INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    current_retry INTEGER DEFAULT 0,
    last_error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    session_id TEXT,
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

CREATE TABLE IF NOT EXISTS templates (
    name TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_run_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER NOT NULL REFERENCES task_logs(id) ON DELETE CASCADE,
    phase TEXT NOT NULL,
    content TEXT,
    duration_ms INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS web_chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,      -- user, assistant
    content TEXT NOT NULL,
    provider TEXT,
    repo TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_task_id ON sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON task_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_run_details_log_id ON task_run_details(log_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_repo ON web_chat_history(repo);
