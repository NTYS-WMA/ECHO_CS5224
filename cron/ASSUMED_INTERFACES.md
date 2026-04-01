# Cron Service v4.0 — Assumed External Interfaces

> This document lists the external service interfaces that the Cron Service
> depends on.  The owning team should confirm or update the contracts.

---

## 1. DB Manager — Scheduled Events API

**Owner**: DB Manager / Platform Team
**Assumed URL**: `http://localhost:18087` (env: `CRON_DB_MANAGER_URL`)

The Cron Service uses DB Manager for all persistence operations on the
`scheduled_events` table.

### 1.1 Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/scheduled-events` | Create a new scheduled event |
| GET | `/scheduled-events/{id}` | Get event by ID |
| GET | `/scheduled-events` | List events with filters |
| GET | `/scheduled-events/due/poll` | Poll for due events (hot path) |
| PUT | `/scheduled-events/{id}` | Update event fields |
| POST | `/scheduled-events/{id}/fired` | Mark event as fired |
| PATCH | `/scheduled-events/{id}/status` | Update event status |
| DELETE | `/scheduled-events/{id}` | Delete event |
| DELETE | `/scheduled-events/by-group/{group_key}` | Batch delete by group |

### 1.2 Authentication

- Header: `X-API-Key` (env: `CRON_DB_MANAGER_API_KEY`)
- Can be disabled if DB Manager runs with `AUTH_ENABLED=false`

---

## 2. Internal Messaging Layer — Event Broker

**Owner**: Platform / Infrastructure Team
**Assumed Broker URL**: `http://localhost:9092` (env: `CRON_EVENT_BROKER_URL`)

### 2.1 Publish Endpoint

```
POST {broker_url}/api/v1/events
```

**Request Body**:

```json
{
  "topic": "proactive.message.send",
  "payload": {
    "event_id": "evt_abc123def456",
    "event_type": "proactive.message.send",
    "source": "cron-service",
    "schema_version": "4.0",
    "timestamp": "2026-04-01T14:00:00Z",
    "scheduled_event_id": "550e8400-...",
    "event_name": "proactive-followup-user123",
    "caller_service": "proactive-message-service",
    "payload": {"user_id": "u123", "template": "follow_up"},
    "correlation_id": "conv456",
    "group_key": "user123"
  }
}
```

**Expected Response `200 OK`**:

```json
{ "status": "accepted" }
```

### 2.2 Topics Published

Topics are dynamically determined by registered events. Common topics include:

| Topic | Description |
|-------|-------------|
| `relationship.decay.requested` | Daily relationship score decay |
| `memory.compaction.requested` | Weekly memory compaction |
| `proactive.message.send` | Proactive message dispatch |
| *(custom)* | Any topic registered by external services |

---

## 3. HTTP Callback Delivery

When an event registers a `callback_url`, the cron service POSTs the
triggered event envelope directly to that URL.

```
POST {callback_url}
Content-Type: application/json

{
  "event_id": "evt_...",
  "event_type": "...",
  "source": "cron-service",
  ...
}
```

**Expected Response**: Any 2xx status code.

---

## Change Log

| Date | Version | Change |
|------|---------|--------|
| 2026-04-01 | 4.0 | Upgrade to event registration service with DB persistence, custom payloads, and HTTP callback delivery. |
| 2026-03-24 | 3.0 | Lightweight event-publishing time trigger. |
| 2026-03-23 | 2.0 | Task scheduler with Database Service and Message Dispatch Hub. |
| 2026-03-23 | 1.0 | Initial version with pipeline-based architecture. |
