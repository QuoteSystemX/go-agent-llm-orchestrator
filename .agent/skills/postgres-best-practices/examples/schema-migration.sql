-- 1. Use snake_case for everything
-- 2. Use TIMESTAMPTZ for all timestamps
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Always index foreign keys
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);

-- 4. Use partial indexes for optimization
CREATE INDEX IF NOT EXISTS idx_public_projects ON projects(created_at) WHERE is_public = TRUE;
