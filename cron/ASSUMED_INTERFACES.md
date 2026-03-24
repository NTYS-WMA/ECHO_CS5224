# Cron Service — Assumed External Interfaces

> **TO BE UPDATED**: This document lists all external service interfaces that the
> Cron Service depends on but are **not yet formally defined** by
> their owning teams. Each section describes the assumed contract. Owning teams
> should review and confirm or revise these contracts.

**Version**: 2.0
**Last Updated**: 2026-03-23

---

## Table of Contents

1. [Database Service — Task CRUD](#1-database-service--task-crud)
2. [Message Dispatch Hub — Send Message](#2-message-dispatch-hub--send-message)
3. [Internal Messaging Layer — Event Broker](#3-internal-messaging-layer--event-broker)

---

## 1. Database Service — Task CRUD

**Owner**: Database Service Team
**Status**: TO BE UPDATED
**Assumed Base URL**: `http://localhost:8010` (env: `CRON_DATABASE_SERVICE_URL`)

The Cron Service relies on the Database Service for **all** persistent
storage of scheduled tasks. It does not maintain its own database.

### 1.1 Create Task — `POST /api/v1/scheduled_tasks`

Store a new scheduled task record.

**Request Body**:

```json
{
  "task_id": "task_a1b2c3d4e5f6",
  "owner_service": "relationship-service",
  "task_type": "one_time",
  "status": "scheduled",
  "channel": "telegram",
  "user_id": "usr_001",
  "conversation_id": "conv_abc",
  "payload": {
    "message_type": "text",
    "content": "Hey, how have you been?",
    "template_id": null,
    "template_variables": null,
    "metadata": {}
  },
  "schedule_config": {
    "scheduled_at": "2026-04-01T09:00:00Z",
    "cron_expression": null,
    "interval_seconds": null,
    "timezone": "UTC",
    "expires_at": null
  },
  "next_run_at": "2026-04-01T09:00:00Z",
  "retry_count": 0,
  "max_retries": 3,
  "priority": 5,
  "tags": ["re-engagement"],
  "created_at": "2026-03-22T18:00:00Z",
  "updated_at": "2026-03-22T18:00:00Z"
}
```

**Expected Response `201 Created`**: The stored task object (echo back).

---

### 1.2 Get Task by ID — `GET /api/v1/scheduled_tasks/{task_id}`

**Expected Response `200 OK`**: Full task object.

**Expected Response `404 Not Found`**: `{ "detail": "Not found" }`

---

### 1.3 List Tasks — `GET /api/v1/scheduled_tasks`

**Query Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `owner_service` | string | Filter by registrant |
| `status` | string | Filter by status |
| `user_id` | string | Filter by user |
| `channel` | string | Filter by channel |
| `tag` | string | Filter by tag |
| `page` | integer | Page number (1-based) |
| `page_size` | integer | Items per page |

**Expected Response `200 OK`**:

```json
{
  "tasks": [ { "...task object..." } ],
  "total": 42
}
```

---

### 1.4 Update Task — `PUT /api/v1/scheduled_tasks/{task_id}`

Partial update. Only provided fields are updated; `updated_at` should be refreshed
server-side.

**Request Body**: Any subset of task fields.

**Expected Response `200 OK`**: Updated task object.

**Expected Response `404 Not Found`**: `{ "detail": "Not found" }`

---

### 1.5 Delete Task — `DELETE /api/v1/scheduled_tasks/{task_id}`

Hard delete or soft delete (set `status=cancelled`).

**Expected Response `200 OK`**: `{ "deleted": true }`

**Expected Response `404 Not Found`**: `{ "detail": "Not found" }`

---

### 1.6 Query Due Tasks — `GET /api/v1/scheduled_tasks/due`

Return tasks where `next_run_at <= now` and `status = scheduled`, ordered by
priority (ascending) then `next_run_at` (ascending).

**Query Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `now` | datetime (ISO 8601) | Current UTC timestamp |
| `limit` | integer | Max tasks to return |

**Expected Response `200 OK`**:

```json
{
  "tasks": [ { "...task object..." } ]
}
```

---

### 1.7 Count Tasks by Status — `GET /api/v1/scheduled_tasks/count`

**Query Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Task status to count |

**Expected Response `200 OK`**:

```json
{
  "count": 15
}
```

---

## 2. Message Dispatch Hub — Send Message

**Owner**: Message Dispatch Hub Team
**Status**: TO BE UPDATED
**Assumed Base URL**: `http://localhost:8020` (env: `CRON_DISPATCH_HUB_URL`)

### 2.1 Send Message — `POST /api/v1/dispatch/send`

Dispatch an outbound message to a user through the specified channel.

**Request Body**:

```json
{
  "event_id": "evt_xxx",
  "task_id": "task_xxx",
  "user_id": "usr_001",
  "channel": "telegram",
  "conversation_id": "conv_abc",
  "message_type": "text",
  "content": "Hey, how have you been?",
  "template_id": null,
  "template_variables": null,
  "metadata": {
    "source": "cron",
    "owner_service": "relationship-service"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | string | Yes | Unique event ID for idempotency |
| `task_id` | string | Yes | Source task ID |
| `user_id` | string | Yes | Target user ID |
| `channel` | string | Yes | Delivery channel |
| `conversation_id` | string | No | Conversation context |
| `message_type` | string | Yes | `text` or `template` |
| `content` | string | Conditional | Message content (for `text` type) |
| `template_id` | string | Conditional | Template ID (for `template` type) |
| `template_variables` | object | No | Template variables |
| `metadata` | object | No | Additional metadata |

**Expected Response `200 OK`**:

```json
{
  "dispatch_id": "dsp_xxx",
  "status": "sent",
  "channel": "telegram",
  "delivered_at": "2026-03-22T18:30:05Z"
}
```

**Expected Error Responses**:

| Status | Meaning |
|--------|---------|
| 400 | Invalid request (missing fields, unknown channel) |
| 404 | User or conversation not found |
| 429 | Rate limited |
| 503 | Channel temporarily unavailable |

---

## 3. Internal Messaging Layer — Event Broker

**Owner**: Platform / Infrastructure Team
**Status**: TO BE UPDATED
**Assumed Broker URL**: `http://localhost:9092` (env: `CRON_EVENT_BROKER_URL`)

The Cron Service publishes lifecycle events to the messaging layer.
The actual broker technology (Kafka, AWS SNS/SQS, Redis Streams, etc.) is to be
confirmed by the platform team.

### 3.1 Topics Published

| Topic | Description |
|-------|-------------|
| `cron.task.dispatched` | Task successfully dispatched to Message Dispatch Hub |
| `cron.task.failed` | Task failed after all retries |

> The Cron Service does **not** publish `conversation.outbound` events.
> That topic is owned by the Channel Gateway Orchestrator.

### 3.2 Expected Publish Interface

The Cron Service POSTs events to `{broker_url}/api/v1/events`:

```python
# HTTP POST to broker
await httpx_client.post(
    f"{broker_url}/api/v1/events",
    json={
        "topic": "cron.task.dispatched",
        "payload": {
            "event_type": "cron.task.dispatched",
            "event_id": "evt_xxx",
            "task_id": "task_xxx",
            "user_id": "usr_xxx",
            "channel": "telegram",
            "owner_service": "relationship-service",
            "dispatched_at": "2026-03-22T18:30:00Z",
            "schema_version": "2.0"
        }
    }
)
```

---

## Change Log

| Date | Version | Change |
|------|---------|--------|
| 2026-03-23 | 2.0 | Complete rewrite. Replaced Relationship/UserProfile/Memory/AI Generation client dependencies with Database Service and Message Dispatch Hub. Service is now a task scheduler, not a pipeline. |
| 2026-03-23 | 1.0 | Initial version with pipeline-based architecture. |
