CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION touch_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_profile_touch_updated_at ON user_profile.user_profile;
CREATE TRIGGER trg_user_profile_touch_updated_at
BEFORE UPDATE ON user_profile.user_profile
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_relationship_scores_touch_updated_at ON relationship_scores;
CREATE TRIGGER trg_relationship_scores_touch_updated_at
BEFORE UPDATE ON relationship_scores
FOR EACH ROW
EXECUTE FUNCTION touch_last_updated();

DROP TRIGGER IF EXISTS trg_memory_history_touch_updated_at ON memory_history;
CREATE TRIGGER trg_memory_history_touch_updated_at
BEFORE UPDATE ON memory_history
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();
