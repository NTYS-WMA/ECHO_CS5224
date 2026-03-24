-- Vector search index for semantic memory retrieval
CREATE INDEX IF NOT EXISTS memories_hnsw_idx
    ON memories USING hnsw (vector vector_cosine_ops);

-- Useful filter/index fields from payload
CREATE INDEX IF NOT EXISTS memories_payload_gin_idx
    ON memories USING gin (payload);

-- Memory history lookup
CREATE INDEX IF NOT EXISTS memory_history_memory_id_idx
    ON memory_history (memory_id);
CREATE INDEX IF NOT EXISTS memory_history_created_at_idx
    ON memory_history (created_at DESC);

-- Relationship query patterns
CREATE INDEX IF NOT EXISTS users_last_active_at_idx
    ON users (last_active_at DESC);
CREATE INDEX IF NOT EXISTS messages_user_id_created_at_idx
    ON messages (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS relationship_scores_score_idx
    ON relationship_scores (score DESC);
CREATE INDEX IF NOT EXISTS relationship_scores_last_updated_idx
    ON relationship_scores (last_updated DESC);
CREATE INDEX IF NOT EXISTS score_history_user_scored_at_idx
    ON score_history (user_id, scored_at DESC);
CREATE INDEX IF NOT EXISTS score_history_scored_at_idx
    ON score_history (scored_at DESC);
