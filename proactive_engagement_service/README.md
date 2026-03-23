# Proactive Engagement Service v2.0

Scheduled task management and polling engine for proactive outbound messaging in the ECHO platform.

---

## Overview

The Proactive Engagement Service is responsible for **receiving, storing, scheduling, and dispatching** proactive outbound messages on behalf of other ECHO services. It acts as a centralized task scheduler — business callers decide **who** to message, **what** to say, and **when** to send; this service stores the task, triggers it on schedule, and dispatches it to the Message Dispatch Hub.

### Core Responsibilities

1. **Task CRUD** — Receive, register, update, pause, resume, and cancel scheduled message tasks from service registrants.
2. **Persistent Storage** — Read/write all task data through the Database Service module (no local database).
3. **Polling Scheduler** — Internal polling loop that periodically discovers due tasks (`next_run_at <= now`) and dispatches them.
4. **Message Dispatch** — Forward due tasks to the Message Dispatch Hub for actual delivery.
5. **Event Publishing** — Publish task lifecycle events (`dispatched`, `failed`) for telemetry.

### What This Service Does NOT Do

- **Candidate selection** — Business callers decide who should receive messages.
- **Prompt assembly** — Business callers assemble message content or provide template IDs.
- **Consent/policy checking** — Business callers enforce their own policies before registering tasks.
- **Database management** — All data is managed by the Database Service module.

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐
│  Service Registrant  │────▶│  Task CRUD APIs       │
│  (Relationship Svc,  │     │  POST/GET/PUT/DELETE  │
│   Orchestrator, etc) │     │  /api/v1/tasks        │
└─────────────────────┘     └──────────┬───────────┘
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │  Database Service     │
                            │  (HTTP API)           │
                            └──────────┬───────────┘
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │  Polling Scheduler    │
                            │  (Background Loop)    │
                            │  every N seconds      │
                            └──────────┬───────────┘
                                       │
                              ┌────────┴────────┐
                              ▼                 ▼
                   ┌──────────────┐  ┌──────────────────┐
                   │ Task Executor │  │  Event Publisher  │
                   └──────┬───────┘  └──────────────────┘
                          │
                          ▼
                   ┌──────────────────┐
                   │ Message Dispatch  │
                   │ Hub (HTTP API)    │
                   └──────────────────┘
```

---

## Directory Structure

```
proactive_engagement_service/
├── __init__.py                  # Package init (v2.0.0)
├── app.py                       # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── API_INTERFACES.md            # API reference for callers
├── ASSUMED_INTERFACES.md        # Assumed external interfaces (TO BE UPDATED)
├── README.md                    # This file
│
├── config/
│   ├── __init__.py
│   └── settings.py              # Environment-based configuration
│
├── models/
│   ├── __init__.py
│   ├── domain.py                # Domain models (ScheduledTask, enums)
│   ├── requests.py              # API request models
│   ├── responses.py             # API response models
│   └── events.py                # Event payload models
│
├── services/
│   ├── __init__.py
│   ├── db_client.py             # Database Service HTTP client
│   ├── dispatcher.py            # Message Dispatch Hub HTTP client
│   ├── task_service.py          # Task CRUD business logic
│   ├── task_executor.py         # Single task execution pipeline
│   └── scheduler.py             # Background polling engine
│
├── routes/
│   ├── __init__.py
│   ├── task_routes.py           # Task CRUD endpoints
│   ├── scheduler_routes.py      # Scheduler control endpoints
│   └── health_routes.py         # Health check endpoints
│
├── events/
│   ├── __init__.py
│   └── publisher.py             # Event publisher (broker placeholder)
│
├── utils/
│   ├── __init__.py
│   └── helpers.py               # ID generation, cron parsing, time utils
│
└── tests/
    ├── __init__.py
    └── test_engagement.py       # Unit tests (40 tests)
```

---

## API Summary

### Task Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/tasks` | Register a new scheduled task |
| GET | `/api/v1/tasks` | List tasks (with filters and pagination) |
| GET | `/api/v1/tasks/{task_id}` | Get a task by ID |
| PUT | `/api/v1/tasks/{task_id}` | Update a task |
| DELETE | `/api/v1/tasks/{task_id}` | Cancel (soft-delete) a task |
| POST | `/api/v1/tasks/{task_id}/pause` | Pause a task |
| POST | `/api/v1/tasks/{task_id}/resume` | Resume a paused task |

### Scheduler Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/scheduler/status` | Get scheduler status |
| POST | `/api/v1/scheduler/trigger` | Manually trigger a poll cycle |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check |

For full API details, see [API_INTERFACES.md](./API_INTERFACES.md).

---

## Task Lifecycle

```
  Register
     │
     ▼
  PENDING ──▶ SCHEDULED ──▶ EXECUTING ──▶ COMPLETED
                  │              │
                  │              ├──▶ FAILED (after max retries)
                  │              │
                  │              └──▶ SCHEDULED (retry / recurring reschedule)
                  │
                  ├──▶ PAUSED ──▶ SCHEDULED (resume)
                  │
                  └──▶ CANCELLED (delete)
```

### Task Types

| Type | Behavior |
|------|----------|
| `one_time` | Executes once at `scheduled_at`, then moves to `completed` |
| `recurring` | Executes on schedule (`cron_expression` or `interval_seconds`), auto-reschedules `next_run_at` |

### Payload Types

| Type | Description |
|------|-------------|
| `text` | Raw message content in `payload.content` |
| `template` | AI Generation template ID in `payload.template_id` with variables |

---

## Configuration

All settings are loaded from environment variables with the `PROACTIVE_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROACTIVE_SERVICE_NAME` | `proactive-engagement-service` | Service name |
| `PROACTIVE_PORT` | `8002` | HTTP port |
| `PROACTIVE_DATABASE_SERVICE_URL` | `http://localhost:8010` | Database Service URL |
| `PROACTIVE_DISPATCH_HUB_URL` | `http://localhost:8020` | Message Dispatch Hub URL |
| `PROACTIVE_POLL_INTERVAL_SECONDS` | `30` | Polling interval (min: 5) |
| `PROACTIVE_MAX_TASKS_PER_POLL` | `100` | Max tasks per poll cycle |
| `PROACTIVE_SCHEDULER_ENABLED` | `true` | Enable background scheduler |
| `PROACTIVE_EVENT_BROKER_URL` | `http://localhost:9092` | Event broker URL |
| `PROACTIVE_LOG_LEVEL` | `INFO` | Logging level |

---

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Start the service
uvicorn proactive_engagement_service.app:app --host 0.0.0.0 --port 8002

# Run tests
python -m pytest proactive_engagement_service/tests/ -v
```

---

## External Dependencies

| Service | Status | Documentation |
|---------|--------|---------------|
| Database Service | TO BE UPDATED | See [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md) §1 |
| Message Dispatch Hub | TO BE UPDATED | See [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md) §2 |
| Internal Messaging Layer | TO BE UPDATED | See [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md) §3 |
