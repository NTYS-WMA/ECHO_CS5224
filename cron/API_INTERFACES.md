# Cron Service v3.0 — API Reference

## 1. Overview

The Cron Service is a lightweight global time-trigger.  It maintains a
schedule table and publishes events to the internal messaging layer when
schedules fire.  It has **no database**, **no task CRUD**, and **no message
dispatch** responsibilities.

### Integration Points

| Direction | Service | Protocol |
|-----------|---------|----------|
| Outbound | Event Broker | HTTP POST `/api/v1/events` |

---

## 2. Schedule APIs

Base URL: `http://localhost:8005`

### 2.1 List Schedules

```
GET /api/v1/schedules
```

**Response `200 OK`**:

```json
{
  "schedules": [
    {
      "name": "relationship-decay",
      "cron_expression": "0 3 * * *",
      "interval_seconds": null,
      "topic": "relationship.decay.requested",
      "payload": {},
      "enabled": true,
      "next_fire_at": "2026-03-25T03:00:00Z",
      "last_fired_at": "2026-03-24T03:00:00Z"
    }
  ],
  "total": 1
}
```

### 2.2 Get Schedule

```
GET /api/v1/schedules/{schedule_name}
```

**Response `200 OK`**: Single `ScheduleEntryResponse` object.

**Response `404`**: Schedule not found.

### 2.3 Scheduler Status

```
GET /api/v1/scheduler/status
```

**Response `200 OK`**:

```json
{
  "running": true,
  "tick_interval_seconds": 30,
  "total_schedules": 2,
  "active_schedules": 2,
  "last_tick_at": "2026-03-24T12:00:00Z"
}
```

### 2.4 Manual Trigger

```
POST /api/v1/scheduler/trigger/{schedule_name}
```

**Request body** (optional):

```json
{
  "payload_override": {"custom": "data"}
}
```

**Response `200 OK`**:

```json
{
  "schedule_name": "relationship-decay",
  "topic": "relationship.decay.requested",
  "published": true,
  "error": null
}
```

**Response `404`**: Schedule not found.

---

## 3. Health APIs

### 3.1 Liveness

```
GET /health
```

**Response `200 OK`**:

```json
{ "status": "healthy", "service": "cron-service" }
```

### 3.2 Readiness

```
GET /ready
```

**Response `200 OK`**:

```json
{ "status": "ready", "service": "cron-service" }
```

---

## 4. Published Events

When a schedule fires, an event is published to the broker.

### Event Envelope

```json
{
  "event_id": "evt_abc123def456",
  "event_type": "<topic>",
  "source": "cron-service",
  "schema_version": "3.0",
  "timestamp": "2026-03-24T03:00:00Z",
  "schedule_name": "<schedule-name>",
  "payload": {}
}
```

### Default Topics

| Topic | Schedule | Frequency |
|-------|----------|-----------|
| `relationship.decay.requested` | `relationship-decay` | Daily 03:00 UTC |
| `memory.compaction.requested` | `memory-compaction` | Weekly Sun 04:00 UTC |

> **Note**: The Cron Service does **not** publish `conversation.outbound`
> or any business-specific events.  It only fires generic time-trigger
> events.  Business services subscribe to these and execute their own logic.

---

## 5. Error Handling

All error responses follow:

```json
{
  "detail": "Human-readable error description"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Request processed successfully |
| 404 | Schedule not found |
| 422 | Request body validation error |
| 500 | Internal server error |
