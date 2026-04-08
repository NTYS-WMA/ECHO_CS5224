-- Prompt template storage for AI Generation Service
CREATE TABLE IF NOT EXISTS prompt_templates (
    template_id VARCHAR(80) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    owner VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,
    variables JSONB NOT NULL DEFAULT '{}'::jsonb,
    defaults JSONB,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_owner ON prompt_templates(owner);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_category ON prompt_templates(category);
