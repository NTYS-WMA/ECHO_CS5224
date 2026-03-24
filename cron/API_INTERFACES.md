# Cron Service — API Interface Reference v2.0

> This document defines all HTTP APIs exposed by the Cron Service.
> Other modules should reference this document when integrating with this service.

**Version**: 2.0
**Last Updated**: 2026-03-23
**Maintained by**: Cron Service Team

---

## Table of Contents

1. [Service Overview](#1-service-overview)
2. [Access Information](#2-access-information)
3. [Task Management APIs](#3-task-management-apis)
4. [Scheduler Control APIs](#4-scheduler-control-apis)
5. [Health Check APIs](#5-health-check-apis)
6. [Published Events](#6-published-events)
7. [Error Handling](#7-error-handling)

---

## 1. Service Overview

The Cron Service v2.0 is a **scheduled task management and polling engine** for proactive outbound messaging in the ECHO platform. It provides:

- **Task CRUD APIs** for service registrants to register, query, update, pause, resume, and cancel scheduled message tasks.
- **Internal polling scheduler** that periodically discovers due tasks and dispatches them to the Message Dispatch Hub.
- **Event publishing** for task lifecycle telemetry.

The service does **not** own business logic for candidate selection or prompt assembly. Business callers decide **who** to message, **what** to say, and **when** to send. This service stores the task, triggers it on schedule, and dispatches it.

**Key integrations**:

| Dependency | Role |
|------------|------|
| Database Service | Persistent storage for all scheduled tasks (via HTTP API) |
| Message Dispatch Hub | Outbound message delivery (via HTTP API) |
| Internal Messaging Layer | Event publishing for telemetry |

---

## 2. Access Information

**Base URL** (internal network):

```
http://<host>:8002
```

**Protocol**: HTTP/1.1, JSON request and response bodies, `Content-Type: application/json`.

**Interactive Docs**: `http://<host>:8002/docs` (Swagger UI)

---

## 3. Task Management APIs

### 3.1 Register Task — `POST /api/v1/tasks`

Create a new scheduled message task.

**Caller**: Any service registrant (e.g., Relationship Service, Conversation Orchestrator).

**Request Body**:

```json
{
  "owner_service": "relationship-service",
  "task_type": "one_time",
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
  "max_retries": 3,
  "priority": 5,
  "tags": ["re-engagement", "high-affinity"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `owner_service` | string | Yes | Name of the registrant service |
| `task_type` | enum | Yes | `one_time` or `recurring` |
| `channel` | string | Yes | Delivery channel (`telegram`, `whatsapp`, `web`) |
| `user_id` | string | Yes | Target user ID |
| `conversation_id` | string | No | Conversation context ID |
| `payload.message_type` | enum | Yes | `text` (raw content) or `template` (AI Generation template) |
| `payload.content` | string | Conditional | Required when `message_type=text` |
| `payload.template_id` | string | Conditional | Required when `message_type=template` |
| `payload.template_variables` | object | No | Variables for template rendering |
| `payload.metadata` | object | No | Arbitrary metadata passed to dispatch |
| `schedule_config.scheduled_at` | datetime | Conditional | For one-time tasks |
| `schedule_config.cron_expression` | string | Conditional | For recurring tasks (standard 5-field cron) |
| `schedule_config.interval_seconds` | integer | Conditional | For recurring tasks (min: 60) |
| `schedule_config.timezone` | string | No | IANA timezone (default: `UTC`) |
| `schedule_config.expires_at` | datetime | No | Auto-cancel after this time |
| `max_retries` | integer | No | Max retry attempts on failure (default: 3) |
| `priority` | integer | No | Priority 1-10, lower = higher (default: 5) |
| `tags` | list[string] | No | Tags for filtering and analytics |

**Response `201 Created`**:

```json
{
  "task_id": "task_a1b2c3d4e5f6",
  "owner_service": "relationship-service",
  "task_type": "one_time",
  "status": "scheduled",
  "channel": "telegram",
  "user_id": "usr_001",
  "payload": { "..." },
  "schedule_config": { "..." },
  "next_run_at": "2026-04-01T09:00:00Z",
  "retry_count": 0,
  "max_retries": 3,
  "priority": 5,
  "tags": ["re-engagement", "high-affinity"],
  "created_at": "2026-03-22T18:00:00Z",
  "updated_at": "2026-03-22T18:00:00Z"
}
```

---

### 3.2 List Tasks — `GET /api/v1/tasks`

Query tasks with filtering and pagination.

**Query Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `owner_service` | string | — | Filter by registrant service |
| `status` | string | — | Filter by status (`scheduled`, `paused`, `executing`, etc.) |
| `user_id` | string | — | Filter by target user |
| `channel` | string | — | Filter by channel |
| `tag` | string | — | Filter by tag |
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Items per page (max: 100) |

**Response `200 OK`**:

```json
{
  "tasks": [ { "...TaskResponse..." } ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

### 3.3 Get Task — `GET /api/v1/tasks/{task_id}`

Retrieve a single task by ID.

**Response `200 OK`**: Full `TaskResponse` object.

**Response `404 Not Found`**:

```json
{ "detail": "Task not found: task_xxx" }
```

---

### 3.4 Update Task — `PUT /api/v1/tasks/{task_id}`

Partial update of a task's payload, schedule, or configuration.

**Request Body (all fields optional)**:

```json
{
  "payload": { "message_type": "text", "content": "Updated message" },
  "schedule_config": { "cron_expression": "0 10 * * 1-5" },
  "max_retries": 5,
  "priority": 3,
  "tags": ["updated-tag"]
}
```

**Response `200 OK`**: Updated `TaskResponse` object.

**Response `404 Not Found`**: Task does not exist.

---

### 3.5 Delete (Cancel) Task — `DELETE /api/v1/tasks/{task_id}`

Soft-deletes a task by setting its status to `cancelled`.

**Response `200 OK`**:

```json
{
  "task_id": "task_xxx",
  "status": "cancelled",
  "message": "Task task_xxx has been cancelled."
}
```

**Response `404 Not Found`**: Task does not exist.

---

### 3.6 Pause Task — `POST /api/v1/tasks/{task_id}/pause`

Pause a scheduled or recurring task. The task will not be picked up by the polling scheduler while paused.

**Response `200 OK`**: Updated `TaskResponse` with `status=paused`.

**Response `400 Bad Request`**: Task not found or not in a pausable state.

---

### 3.7 Resume Task — `POST /api/v1/tasks/{task_id}/resume`

Resume a previously paused task.

**Response `200 OK`**: Updated `TaskResponse` with `status=scheduled`.

**Response `400 Bad Request`**: Task not found or not in a resumable state.

---

## 4. Scheduler Control APIs

### 4.1 Get Scheduler Status — `GET /api/v1/scheduler/status`

Returns the current state of the polling engine.

**Response `200 OK`**:

```json
{
  "running": true,
  "poll_interval_seconds": 30,
  "last_poll_at": "2026-03-22T18:30:00Z",
  "tasks_pending": 15,
  "tasks_executing": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `running` | boolean | Whether the background scheduler is active |
| `poll_interval_seconds` | integer | Configured polling interval |
| `last_poll_at` | datetime | Timestamp of the last completed poll cycle |
| `tasks_pending` | integer | Tasks in `scheduled` status |
| `tasks_executing` | integer | Tasks currently being executed |

---

### 4.2 Manual Poll Trigger — `POST /api/v1/scheduler/trigger`

Trigger a single poll cycle manually (for testing / ops). Does not affect the background polling loop schedule.

**Request Body (optional)**:

```json
{
  "max_tasks": 50
}
```

**Response `200 OK`**:

```json
{
  "poll_id": "poll_abc123",
  "tasks_found": 5,
  "tasks_dispatched": 4,
  "tasks_failed": 1,
  "results": [
    { "task_id": "task_001", "success": true, "error": null },
    { "task_id": "task_002", "success": false, "error": "dispatch timeout" }
  ],
  "duration_ms": 245.3
}
```

---

## 5. Health Check APIs

### 5.1 Liveness — `GET /health`

```json
{ "status": "healthy", "service": "cron-service" }
```

### 5.2 Readiness — `GET /ready`

```json
{ "status": "ready", "service": "cron-service" }
```

---

## 6. Published Events

Events published to the Internal Messaging Layer for downstream consumers.

### 6.1 `proactive.task.dispatched`

Published when a task is successfully dispatched to the Message Dispatch Hub.

```json
{
  "event_type": "proactive.task.dispatched",
  "event_id": "evt_xxx",
  "task_id": "task_xxx",
  "user_id": "usr_xxx",
  "channel": "telegram",
  "owner_service": "relationship-service",
  "dispatched_at": "2026-03-22T18:30:00Z",
  "schema_version": "2.0"
}
```

### 6.2 `proactive.task.failed`

Published when a task exhausts all retries and fails permanently.

```json
{
  "event_type": "proactive.task.failed",
  "event_id": "evt_xxx",
  "task_id": "task_xxx",
  "user_id": "usr_xxx",
  "owner_service": "relationship-service",
  "error": "Message Dispatch Hub returned 503",
  "retry_count": 3,
  "failed_at": "2026-03-22T18:30:00Z",
  "schema_version": "2.0"
}
```

### 6.3 `conversation.outbound`

Published as the dispatch payload sent to the Message Dispatch Hub.

```json
{
  "event_type": "conversation.outbound",
  "event_id": "evt_xxx",
  "task_id": "task_xxx",
  "user_id": "usr_xxx",
  "channel": "telegram",
  "content": "Hey, how have you been?",
  "message_type": "text",
  "metadata": {},
  "schema_version": "2.0"
}
```

---

## 7. Error Handling

All error responses follow a consistent format:

```json
{
  "detail": "Human-readable error description"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 201 | Resource created successfully |
| 200 | Request processed successfully |
| 400 | Bad request or invalid state transition |
| 404 | Resource not found |
| 422 | Request body validation error |
| 500 | Internal server error |
