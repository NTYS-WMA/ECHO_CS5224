-- Scheduled events table for the Cron Service v4.0
-- Supports one-time and recurring events registered by external services

CREATE TABLE IF NOT EXISTS scheduled_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event identity
    event_name VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL DEFAULT 'one_time',
        -- one_time: fires once then completes
        -- recurring: fires repeatedly on cron/interval schedule

    -- Who registered this event
    caller_service VARCHAR(64) NOT NULL,
    -- Where to deliver the event (topic or callback URL)
    callback_url VARCHAR(512),
    topic VARCHAR(128),

    -- Schedule definition (exactly one should be set for recurring)
    cron_expression VARCHAR(64),
    interval_seconds INTEGER CHECK (interval_seconds IS NULL OR interval_seconds >= 10),
    -- For one-time events: the exact time to fire
    scheduled_at TIMESTAMPTZ,

    -- Flexible payload — each caller can put whatever it needs
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Event lifecycle
    status VARCHAR(16) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed', 'cancelled', 'failed')),
    next_fire_at TIMESTAMPTZ,
    last_fired_at TIMESTAMPTZ,
    fire_count INTEGER NOT NULL DEFAULT 0,
    max_fires INTEGER,  -- NULL = unlimited for recurring

    -- Context for tracing
    correlation_id VARCHAR(128),
    -- Caller-defined grouping key (e.g. user_id for proactive messages)
    group_key VARCHAR(128),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index: poll for due events (the hot query)
CREATE INDEX IF NOT EXISTS idx_scheduled_events_due
    ON scheduled_events (next_fire_at ASC)
    WHERE status = 'active' AND next_fire_at IS NOT NULL;

-- Index: lookup by caller
CREATE INDEX IF NOT EXISTS idx_scheduled_events_caller
    ON scheduled_events (caller_service, status);

-- Index: lookup by group_key (e.g. find all events for a user)
CREATE INDEX IF NOT EXISTS idx_scheduled_events_group_key
    ON scheduled_events (group_key)
    WHERE group_key IS NOT NULL;

-- Index: lookup by event_name
CREATE INDEX IF NOT EXISTS idx_scheduled_events_name
    ON scheduled_events (event_name, status);

-- Trigger: auto-update updated_at
DROP TRIGGER IF EXISTS trg_scheduled_events_touch_updated_at ON scheduled_events;
CREATE TRIGGER trg_scheduled_events_touch_updated_at
BEFORE UPDATE ON scheduled_events
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();
