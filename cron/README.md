# Cron Service v4.0

Event registration and trigger service for the ECHO platform.

---

## Overview

The Cron Service has been upgraded from a simple config-driven time trigger to a **full-featured event registration and scheduling service**. External services register scheduled events via API; the cron engine polls the database for due events and dispatches them via the event broker or direct HTTP callbacks.

### Core Responsibilities

1. **Event Registration API** — External services register one-time or recurring events with custom payloads.
2. **Database-Backed Persistence** — All events are stored in PostgreSQL (via DB Manager), surviving restarts.
3. **Polling & Dispatch** — Background tick loop polls for due events and fires them.
4. **Status Lifecycle** — Events transition through states: `active` → `completed`/`cancelled`/`failed`.
5. **Flexible Payload** — Each event carries a JSONB payload customized by the caller (user_id, conversation context, template names, etc.).
6. **Dual Delivery** — Dispatch via event broker topic AND/OR direct HTTP callback URL.

### What Changed from v3.0

| v3.0 | v4.0 |
|------|------|
| In-memory schedule table from config | Database-backed events via DB Manager |
| No external registration API | Full CRUD API for event registration |
| Fixed schedules only | One-time + recurring events |
| Topic-only delivery | Topic + HTTP callback delivery |
| No state management | Full lifecycle (active/paused/completed/cancelled/failed) |
| No custom payloads | JSONB payload per event |
| No grouping | Group key for batch operations |

### Architecture

```
┌─────────────────────────┐
│  External Services       │  proactive-message, relationship, memory, etc.
│  POST /api/v1/events     │  Register scheduled events
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│   Cron Service (v4.0)    │
│                          │
│  ┌────────────────────┐  │
│  │ Event Registration  │  │  REST API for CRUD
│  │ API                 │  │
│  └────────┬───────────┘  │
│           │              │
│  ┌────────▼───────────┐  │
│  │ DB Manager Client   │  │  HTTP calls to DB Manager
│  └────────┬───────────┘  │
│           │              │
│  ┌────────▼───────────┐  │
│  │ CronScheduler       │  │  Background tick loop (every 30s)
│  │ - Poll due events   │  │  next_fire_at <= now?
│  │ - Fire events       │  │
│  │ - Update status     │  │
│  └────────┬───────────┘  │
│           │              │
│  ┌────────▼───────────┐  │
│  │ EventPublisher      │  │  Dual delivery:
│  │ - Broker topic      │  │    POST {broker}/api/v1/events
│  │ - HTTP callback     │  │    POST {callback_url}
│  └────────────────────┘  │
└──────────────────────────┘
           │
           ▼
┌─────────────────────────┐     ┌──────────────────────────┐
│   Event Broker           │     │  DB Manager (PostgreSQL)  │
│   (Internal Bus)         │     │  scheduled_events table   │
└──────────┬──────────────┘     └──────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│  Business Consumers      │  Relationship Service, Memory Service,
│                          │  Proactive Message Service, etc.
└─────────────────────────┘
```

---

## Database Schema

The `scheduled_events` table is managed by DB Manager in PostgreSQL:

```sql
CREATE TABLE scheduled_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL DEFAULT 'one_time',  -- one_time | recurring
    caller_service VARCHAR(64) NOT NULL,
    callback_url VARCHAR(512),
    topic VARCHAR(128),
    cron_expression VARCHAR(64),
    interval_seconds INTEGER,
    scheduled_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(16) NOT NULL DEFAULT 'active',  -- active|paused|completed|cancelled|failed
    next_fire_at TIMESTAMPTZ,
    last_fired_at TIMESTAMPTZ,
    fire_count INTEGER NOT NULL DEFAULT 0,
    max_fires INTEGER,           -- NULL = unlimited
    correlation_id VARCHAR(128),
    group_key VARCHAR(128),      -- e.g. user_id for batch ops
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Event Lifecycle

```
                 register
                    │
                    ▼
              ┌──────────┐
              │  active   │◄─── resume
              └────┬─────┘
                   │
          ┌────────┼────────┐
          │        │        │
          ▼        ▼        ▼
    ┌──────────┐  fire  ┌────────┐
    │  paused  │───→    │ cancel │
    └──────────┘        └────────┘
                   │
          ┌────────┼────────┐
          │                 │
          ▼                 ▼
    ┌──────────┐     ┌──────────┐
    │completed │     │  failed  │
    │(one-time │     │(dispatch │
    │ or max   │     │ error)   │
    │ reached) │     └──────────┘
    └──────────┘
```

---

## Directory Structure

```
cron/
├── __init__.py                  # Package init (v4.0.0)
├── app.py                       # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── ASSUMED_INTERFACES.md        # External service contracts
│
├── config/
│   ├── __init__.py
│   └── settings.py              # Environment-based configuration
│
├── clients/
│   ├── __init__.py
│   └── db_manager_client.py     # HTTP client for DB Manager
│
├── models/
│   ├── __init__.py
│   ├── domain.py                # ScheduledEvent + legacy ScheduleEntry
│   ├── events.py                # CronTriggeredEvent envelope
│   ├── requests.py              # API request models
│   └── responses.py             # API response models
│
├── services/
│   ├── __init__.py
│   └── scheduler.py             # CronScheduler — DB-backed tick engine
│
├── routes/
│   ├── __init__.py
│   ├── event_routes.py          # Event registration & management API
│   ├── schedule_routes.py       # Legacy routes (backward compat)
│   └── health_routes.py         # Health check endpoints
│
├── events/
│   ├── __init__.py
│   └── publisher.py             # Event broker + HTTP callback publisher
│
├── utils/
│   ├── __init__.py
│   └── helpers.py               # ID generation, cron parsing
│
└── tests/
    ├── __init__.py
    └── test_engagement.py       # Unit tests
```

---

## API Summary

### Event Registration & Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/events` | Register a new scheduled event |
| GET | `/api/v1/events` | List events (with filters) |
| GET | `/api/v1/events/{id}` | Get a single event |
| PUT | `/api/v1/events/{id}` | Update an event |
| DELETE | `/api/v1/events/{id}` | Delete an event |
| DELETE | `/api/v1/events/by-group/{group_key}` | Delete all events for a group |
| POST | `/api/v1/events/{id}/cancel` | Cancel an event |
| POST | `/api/v1/events/{id}/pause` | Pause an event |
| POST | `/api/v1/events/{id}/resume` | Resume a paused event |
| POST | `/api/v1/events/{id}/trigger` | Manually trigger an event |

### Scheduler

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/scheduler/status` | Get scheduler status |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check |

---

## Usage Examples

### 1. Register a One-Time Proactive Message Event

A proactive message service schedules a follow-up message to a user 2 hours after their last conversation:

```bash
curl -X POST http://localhost:8005/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "proactive-followup-user123",
    "event_type": "one_time",
    "caller_service": "proactive-message-service",
    "topic": "proactive.message.send",
    "scheduled_at": "2026-04-01T14:00:00Z",
    "payload": {
      "user_id": "user123",
      "conversation_id": "conv456",
      "message_template": "follow_up",
      "context": "User was discussing learning Python"
    },
    "group_key": "user123",
    "correlation_id": "conv456"
  }'
```

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "event_name": "proactive-followup-user123",
  "event_type": "one_time",
  "status": "active",
  "next_fire_at": "2026-04-01T14:00:00Z",
  "message": "Event registered successfully."
}
```

### 2. Register a Recurring Relationship Decay Event

```bash
curl -X POST http://localhost:8005/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "relationship-decay",
    "event_type": "recurring",
    "caller_service": "cron-service",
    "topic": "relationship.decay.requested",
    "cron_expression": "0 3 * * *",
    "payload": {}
  }'
```

### 3. Register a Recurring Event with Callback URL

```bash
curl -X POST http://localhost:8005/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "daily-user-digest",
    "event_type": "recurring",
    "caller_service": "notification-service",
    "callback_url": "http://notification-service:8010/api/v1/digest/trigger",
    "cron_expression": "0 8 * * *",
    "payload": {
      "digest_type": "daily",
      "channels": ["email", "telegram"]
    },
    "max_fires": 30
  }'
```

### 4. Cancel All Events for a User

When a user opts out or deactivates, cancel all their scheduled events:

```bash
curl -X DELETE http://localhost:8005/api/v1/events/by-group/user123
```

### 5. Query Events by Caller Service

```bash
curl "http://localhost:8005/api/v1/events?caller_service=proactive-message-service&status=active"
```

---

## Published Event Envelope

When a scheduled event fires, the following JSON is published:

```json
{
  "event_id": "evt_abc123def456",
  "event_type": "proactive.message.send",
  "source": "cron-service",
  "schema_version": "4.0",
  "timestamp": "2026-04-01T14:00:00Z",
  "scheduled_event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_name": "proactive-followup-user123",
  "caller_service": "proactive-message-service",
  "payload": {
    "user_id": "user123",
    "conversation_id": "conv456",
    "message_template": "follow_up",
    "context": "User was discussing learning Python"
  },
  "correlation_id": "conv456",
  "group_key": "user123"
}
```

---

## Configuration

All settings are loaded from environment variables with the `CRON_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRON_SERVICE_NAME` | `cron-service` | Service name |
| `CRON_PORT` | `8005` | HTTP port |
| `CRON_DB_MANAGER_URL` | `http://localhost:18087` | DB Manager URL |
| `CRON_DB_MANAGER_TIMEOUT` | `10` | DB Manager timeout (seconds) |
| `CRON_DB_MANAGER_API_KEY` | `""` | DB Manager API key |
| `CRON_EVENT_BROKER_URL` | `http://localhost:9092` | Event broker URL |
| `CRON_EVENT_PUBLISH_TIMEOUT` | `5` | Publish timeout (seconds) |
| `CRON_EVENT_PUBLISH_RETRIES` | `2` | Publish retry count |
| `CRON_TICK_INTERVAL_SECONDS` | `30` | Scheduler tick interval (min: 5) |
| `CRON_SCHEDULES_JSON` | `""` | Built-in schedules (JSON array) |
| `CRON_AUTO_REGISTER_DEFAULTS` | `true` | Auto-register defaults on startup |
| `CRON_LOG_LEVEL` | `INFO` | Logging level |

### Default Schedules (auto-registered)

| Schedule | Cron | Topic |
|----------|------|-------|
| `relationship-decay` | `0 3 * * *` | `relationship.decay.requested` |
| `memory-compaction` | `0 4 * * 0` | `memory.compaction.requested` |

---

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Start the service (requires DB Manager to be running)
uvicorn cron.app:app --host 0.0.0.0 --port 8005

# Run tests
python -m pytest cron/tests/ -v
```

---

## Proactive Message Integration

The cron service is designed to support the **proactive message** feature. Here's the typical flow:

1. After a conversation ends, the proactive message service analyzes the conversation and decides whether to send a follow-up.
2. If yes, it calls `POST /api/v1/events` to register a one-time event with the user's context in the payload.
3. When the scheduled time arrives, the cron service fires the event to the `proactive.message.send` topic.
4. The proactive message service receives the event, retrieves the conversation context from the payload, generates a message, and sends it.

```
User conversation ends
        │
        ▼
Proactive Service analyzes conversation
        │
        ▼
POST /api/v1/events
  event_name: "followup-user123"
  scheduled_at: now + 2 hours
  payload: {user_id, conversation_id, context}
  group_key: "user123"
        │
        ▼
Cron Service stores in DB
        │
        ▼  (2 hours later)
Cron fires → proactive.message.send topic
        │
        ▼
Proactive Service generates & sends message
```

This pattern allows:
- **Cancellation**: If the user starts a new conversation before the timer, delete events by group_key.
- **Rescheduling**: Update the event's `scheduled_at` if the user is active again.
- **Batch cleanup**: Delete all events for a deactivated user.
