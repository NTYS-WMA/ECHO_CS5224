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
    school_name VARCHAR(200),
    grade VARCHAR(50),
    class_name VARCHAR(50)
);

-- Relationship service owned tables
CREATE TABLE IF NOT EXISTS relationship_scores (
    user_id VARCHAR(50) PRIMARY KEY,
    score NUMERIC(5,4) NOT NULL DEFAULT 0.1000 CHECK (score >= 0.0 AND score <= 1.0),
    tier VARCHAR(32) NOT NULL DEFAULT 'acquaintance',
    total_interactions INTEGER NOT NULL DEFAULT 0,
    positive_interactions INTEGER NOT NULL DEFAULT 0,
    negative_interactions INTEGER NOT NULL DEFAULT 0,
    last_interaction_at TIMESTAMPTZ,
    last_scored_at TIMESTAMPTZ,
    last_decay_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS score_history (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    delta NUMERIC(6,4) NOT NULL,
    old_score NUMERIC(5,4),
    new_score NUMERIC(5,4) NOT NULL CHECK (new_score >= 0.0 AND new_score <= 1.0),
    sentiment VARCHAR(32),
    intensity NUMERIC(5,4),
    reason TEXT,
    reasoning TEXT,
    source VARCHAR(32) NOT NULL DEFAULT 'unknown',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

