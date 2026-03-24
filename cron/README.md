# Cron Service v3.0

Lightweight global time-trigger service for the ECHO platform.

---

## Overview

The Cron Service is a **pure scheduling infrastructure component**. It maintains an in-memory schedule table (cron tabs) and, when a scheduled time arrives, publishes the corresponding event to the internal messaging layer (event broker). Business services subscribe to these events and execute their own domain logic.

### Core Responsibilities

1. **Schedule Management** — Maintain a table of named cron schedules loaded from configuration.
2. **Time Triggering** — Background tick loop checks for due schedules and fires them.
3. **Event Publishing** — Publish events to the broker via HTTP when schedules fire.
4. **Operational APIs** — Health checks, schedule listing, and manual trigger for ops/testing.

### What This Service Does NOT Do

- **Business logic** — No knowledge of relationship scoring, message content, user profiles, etc.
- **Task CRUD** — No database. Schedules are defined in configuration.
- **Message dispatch** — No direct connection to Message Dispatch Hub or channel gateways.
- **Retry / state management** — Downstream consumers handle their own retries.

### Architecture Principle

```
┌──────────────────────┐
│    Configuration     │  (JSON env var or defaults)
│    ┌───────────┐     │
│    │ Schedule 1 │     │  name: relationship-decay
│    │ Schedule 2 │     │  name: memory-compaction
│    │ ...        │     │
│    └───────────┘     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   CronScheduler      │  Background tick loop (every N seconds)
│   ┌──────────────┐   │
│   │ Check due     │   │  next_fire_at <= now?
│   │ schedules     │   │
│   └──────┬───────┘   │
│          │            │
│          ▼            │
│   ┌──────────────┐   │
│   │ EventPublisher│   │  POST {broker}/api/v1/events
│   └──────────────┘   │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│   Event Broker       │  relationship.decay.requested
│   (Internal Bus)     │  memory.compaction.requested
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│  Business Consumers  │  Relationship Service, Memory Service, etc.
└──────────────────────┘
```

---

## Directory Structure

```
cron/
├── __init__.py                  # Package init (v3.0.0)
├── app.py                       # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── README.md                    # This file
│
├── config/
│   ├── __init__.py
│   └── settings.py              # Environment-based configuration + schedule defs
│
├── models/
│   ├── __init__.py
│   ├── domain.py                # ScheduleEntry model
│   ├── events.py                # CronTriggeredEvent model
│   ├── requests.py              # API request models
│   └── responses.py             # API response models
│
├── services/
│   ├── __init__.py
│   └── scheduler.py             # CronScheduler — background tick engine
│
├── routes/
│   ├── __init__.py
│   ├── schedule_routes.py       # Schedule listing & manual trigger
│   └── health_routes.py         # Health check endpoints
│
├── events/
│   ├── __init__.py
│   └── publisher.py             # HTTP event publisher
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

### Schedules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/schedules` | List all configured schedules |
| GET | `/api/v1/schedules/{name}` | Get a single schedule |
| GET | `/api/v1/scheduler/status` | Get scheduler status |
| POST | `/api/v1/scheduler/trigger/{name}` | Manually trigger a schedule |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check |

---

## Published Events

When a schedule fires, the service publishes an event to the configured topic:

```json
{
  "event_id": "evt_abc123def456",
  "event_type": "relationship.decay.requested",
  "source": "cron-service",
  "schema_version": "3.0",
  "timestamp": "2026-03-24T03:00:00Z",
  "schedule_name": "relationship-decay",
  "payload": {}
}
```

### Default Schedules

| Schedule | Cron | Topic | Description |
|----------|------|-------|-------------|
| `relationship-decay` | `0 3 * * *` | `relationship.decay.requested` | Daily at 03:00 UTC |
| `memory-compaction` | `0 4 * * 0` | `memory.compaction.requested` | Weekly Sunday at 04:00 UTC |

---

## Configuration

All settings are loaded from environment variables with the `CRON_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRON_SERVICE_NAME` | `cron-service` | Service name |
| `CRON_PORT` | `8005` | HTTP port |
| `CRON_EVENT_BROKER_URL` | `http://localhost:9092` | Event broker URL |
| `CRON_EVENT_PUBLISH_TIMEOUT` | `5` | Publish timeout (seconds) |
| `CRON_EVENT_PUBLISH_RETRIES` | `2` | Publish retry count |
| `CRON_TICK_INTERVAL_SECONDS` | `30` | Scheduler tick interval (min: 5) |
| `CRON_SCHEDULES_JSON` | `""` | Custom schedules (JSON array) |
| `CRON_LOG_LEVEL` | `INFO` | Logging level |

### Custom Schedules via Environment

Set `CRON_SCHEDULES_JSON` to override the default schedule table:

```bash
export CRON_SCHEDULES_JSON='[
  {"name":"relationship-decay","cron_expression":"0 3 * * *","topic":"relationship.decay.requested"},
  {"name":"proactive-scan","cron_expression":"0 9 * * 1-5","topic":"proactive.scan.requested"}
]'
```

---

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Start the service
uvicorn cron.app:app --host 0.0.0.0 --port 8005

# Run tests
python -m pytest cron/tests/ -v
```
