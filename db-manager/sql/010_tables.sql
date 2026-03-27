-- Memory vector storage (from Memory Manager requirement)
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY,
    vector VECTOR(1536) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Memory history moved from SQLite to PostgreSQL
CREATE TABLE IF NOT EXISTS memory_history (
    id UUID PRIMARY KEY,
    memory_id UUID NOT NULL,
    old_memory TEXT,
    new_memory TEXT,
    event VARCHAR(16) NOT NULL CHECK (event IN ('ADD', 'UPDATE', 'DELETE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    actor_id VARCHAR(64),
    role VARCHAR(16)
);

-- Basic user profile extracted from conversation (non-authoritative)
CREATE TABLE IF NOT EXISTS user_profile.user_profile (
    user_id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    name VARCHAR(100),
    nickname VARCHAR(100),
    english_name VARCHAR(100),
    birthday DATE,
    gender VARCHAR(10),
    nationality VARCHAR(50),
    hometown VARCHAR(100),
    current_city VARCHAR(100),
    timezone VARCHAR(50),
    language VARCHAR(50),
    occupation VARCHAR(100),
    company VARCHAR(200),
    education_level VARCHAR(50),
    university VARCHAR(200),
    major VARCHAR(100)
);

-- Relationship service owned tables
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(16) PRIMARY KEY,
    telegram_id BIGINT,
    first_name VARCHAR(128),
    onboarding_complete BOOLEAN NOT NULL DEFAULT FALSE,
    last_active_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(16) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(16),
    content TEXT,
    is_proactive BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS relationship_scores (
    user_id VARCHAR(16) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    score NUMERIC(5,4) NOT NULL DEFAULT 0.1000 CHECK (score >= 0.0 AND score <= 1.0),
    total_interactions INTEGER NOT NULL DEFAULT 0,
    positive_interactions INTEGER NOT NULL DEFAULT 0,
    negative_interactions INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_scored_at TIMESTAMPTZ,
    last_decay_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS score_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(16) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta NUMERIC(6,4) NOT NULL,
    new_score NUMERIC(5,4) NOT NULL CHECK (new_score >= 0.0 AND new_score <= 1.0),
    sentiment VARCHAR(16),
    intensity VARCHAR(16),
    reason VARCHAR(32) NOT NULL,
    reasoning TEXT,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
