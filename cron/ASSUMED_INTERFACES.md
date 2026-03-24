# Cron Service — Assumed External Interfaces

> This document lists the external service interface that the Cron Service
> depends on.  The owning team should confirm or update the contract.

---

## 1. Internal Messaging Layer — Event Broker

**Owner**: Platform / Infrastructure Team
**Assumed Broker URL**: `http://localhost:9092` (env: `CRON_EVENT_BROKER_URL`)

The Cron Service publishes time-trigger events to the messaging layer
via HTTP POST.

### 1.1 Publish Endpoint

```
POST {broker_url}/api/v1/events
```

**Request Body**:

```json
{
  "topic": "relationship.decay.requested",
  "payload": {
    "event_id": "evt_abc123def456",
    "event_type": "relationship.decay.requested",
    "source": "cron-service",
    "schema_version": "3.0",
    "timestamp": "2026-03-24T03:00:00Z",
    "schedule_name": "relationship-decay",
    "payload": {}
  }
}
```

**Expected Response `200 OK`**:

```json
{ "status": "accepted" }
```

### 1.2 Topics Published

| Topic | Description |
|-------|-------------|
| `relationship.decay.requested` | Time to run relationship decay scoring |
| `memory.compaction.requested` | Time to run memory compaction |

> Additional topics can be added via `CRON_SCHEDULES_JSON` configuration
> without code changes.

---

## Change Log

| Date | Version | Change |
|------|---------|--------|
| 2026-03-24 | 3.0 | Complete rewrite. Reduced to lightweight event-publishing time trigger. Removed Database Service, Message Dispatch Hub, and task CRUD dependencies. |
| 2026-03-23 | 2.0 | Task scheduler architecture with Database Service and Message Dispatch Hub. |
| 2026-03-23 | 1.0 | Initial version with pipeline-based architecture. |
