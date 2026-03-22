# Proactive Engagement Service — API Interface Reference

**Version**: 1.0  
**Last Updated**: 2026-03-23  
**Maintained by**: Proactive Engagement Service Team

---

## Table of Contents

1. [Service Overview](#1-service-overview)
2. [Access Information](#2-access-information)
3. [API Endpoints](#3-api-endpoints)
   - [POST /api/v1/proactive/trigger](#31-post-apiv1proactivetrigger)
   - [GET /api/v1/proactive/status](#32-get-apiv1proactivestatus)
   - [GET /health](#33-get-health)
   - [GET /ready](#34-get-ready)
4. [Consumed Events](#4-consumed-events)
   - [proactive.scan.requested](#41-proactivescanrequested)
5. [Published Events](#5-published-events)
   - [conversation.outbound](#51-conversationoutbound)
   - [proactive.dispatch.completed](#52-proactivedispatchcompleted)
6. [Error Handling](#6-error-handling)
7. [Data Models](#7-data-models)
8. [Pipeline Flow](#8-pipeline-flow)

---

## 1. Service Overview

The Proactive Engagement Service determines when ECHO should initiate outbound engagement with users. It manages the full pipeline from candidate selection through policy checking to message dispatch. The service operates primarily in an event-driven manner, consuming scan trigger events from the platform scheduler, but also exposes a manual trigger API for operational use.

**Responsibilities**:

- Consume proactive scan trigger events from the messaging layer.
- Search for engagement candidates via the Relationship Service.
- Enforce consent and quiet-hours policies via the User Profile Service.
- Retrieve recent memory summaries via the Memory Service for personalization.
- Request AI-generated proactive messages via the AI Generation Service.
- Publish outbound message events for channel delivery.
- Publish dispatch telemetry events for monitoring and observability.

---

## 2. Access Information

**Base URL** (internal network):

```
http://<host>:8006
```

| Port | Purpose                                  |
|------|------------------------------------------|
| 8006 | Proactive Engagement Service main API    |

**Protocol**: HTTP/1.1, JSON request and response bodies, `Content-Type: application/json`.

**Interactive Docs**: `http://<host>:8006/docs` (Swagger UI)

---

## 3. API Endpoints

### 3.1 POST /api/v1/proactive/trigger

Manually trigger a proactive engagement scan. This endpoint is intended for operational use and testing. In production, scans are triggered by the platform scheduler via the `proactive.scan.requested` event.

**Source**: Operations / Admin  
**Type**: Internal synchronous API call

**Request body**:

```json
{
  "timezone": "Asia/Singapore",
  "filters": {
    "min_days_inactive": 3,
    "min_affinity_score": 0.5,
    "max_batch_size": 500
  },
  "correlation_id": "manual-trigger-001"
}
```

| Field            | Type   | Required | Description                                         |
|------------------|--------|----------|-----------------------------------------------------|
| `timezone`       | string | no       | Target timezone (default: `Asia/Singapore`)         |
| `filters`        | object | no       | Custom candidate selection filters (defaults used)  |
| `correlation_id` | string | no       | Correlation ID for distributed tracing              |

**`filters` fields**:

| Field                | Type    | Default | Description                                |
|----------------------|---------|---------|--------------------------------------------|
| `min_days_inactive`  | integer | 3       | Minimum days of inactivity (>=1)           |
| `min_affinity_score` | float   | 0.5     | Minimum affinity score (0.0-1.0)           |
| `max_batch_size`     | integer | 500     | Maximum candidates per scan (1-10000)      |

**Response** `200 OK`:

```json
{
  "scan_id": "scan-abc123",
  "status": "completed",
  "candidates_scanned": 500,
  "messages_dispatched": 127,
  "messages_skipped": 373,
  "results": [
    {
      "user_id": "usr_9f2a7c41",
      "dispatched": true,
      "skip_reason": null
    },
    {
      "user_id": "usr_b3d8e012",
      "dispatched": false,
      "skip_reason": "consent_denied"
    }
  ]
}
```

| Field                 | Type    | Description                                    |
|-----------------------|---------|------------------------------------------------|
| `scan_id`             | string  | Unique scan identifier                         |
| `status`              | string  | `running`, `completed`, or `failed`            |
| `candidates_scanned`  | integer | Total candidates evaluated                     |
| `messages_dispatched` | integer | Messages successfully dispatched               |
| `messages_skipped`    | integer | Candidates skipped due to policy checks        |
| `results`             | array   | Per-candidate dispatch results (optional)      |

**`results[*]` fields**:

| Field         | Type    | Description                                            |
|---------------|---------|--------------------------------------------------------|
| `user_id`     | string  | Internal user identifier                               |
| `dispatched`  | boolean | Whether the message was dispatched                     |
| `skip_reason` | string  | Reason for skipping (null if dispatched)               |

**Possible `skip_reason` values**:

| Value                     | Description                                        |
|---------------------------|----------------------------------------------------|
| `consent_denied`          | User has not consented to proactive messaging      |
| `quiet_hours`             | Current time is within user's quiet hours          |
| `profile_unavailable`     | User profile could not be retrieved                |
| `channel_info_unavailable`| User channel/conversation info unavailable         |
| `generation_failed`       | AI Generation Service failed to produce a message  |
| `generation_empty`        | AI Generation Service returned empty content       |
| `publish_failed`          | Failed to publish outbound event                   |

---

### 3.2 GET /api/v1/proactive/status

Returns the current operational status of the Proactive Engagement Service.

**Response** `200 OK`:

```json
{
  "service": "proactive-engagement-service",
  "status": "running",
  "scan_mode": "event-driven + manual",
  "topics_consumed": ["proactive.scan.requested"],
  "topics_published": ["conversation.outbound", "proactive.dispatch.completed"]
}
```

---

### 3.3 GET /health

Basic liveness check.

**Response** `200 OK`:

```json
{
  "status": "healthy",
  "service": "proactive-engagement-service"
}
```

---

### 3.4 GET /ready

Readiness check.

**Response** `200 OK`:

```json
{
  "status": "ready",
  "service": "proactive-engagement-service"
}
```

---

## 4. Consumed Events

### 4.1 proactive.scan.requested

Consumed from the Internal Asynchronous Messaging Layer. Published by the platform scheduler to trigger a proactive engagement scan.

**Topic**: `proactive.scan.requested`

```json
{
  "event_id": "evt-7001",
  "event_type": "proactive.scan.requested",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T01:00:00Z",
  "window": {
    "timezone": "Asia/Singapore",
    "hour": 9
  },
  "mode": "scheduled"
}
```

| Field            | Type   | Description                                    |
|------------------|--------|------------------------------------------------|
| `event_id`       | string | Unique event identifier                        |
| `event_type`     | string | Always `proactive.scan.requested`              |
| `schema_version` | string | Schema version for forward compatibility       |
| `timestamp`      | string | ISO 8601 timestamp of the trigger              |
| `window`         | object | Time window context (timezone, hour)           |
| `mode`           | string | `scheduled` or `manual`                        |

---

## 5. Published Events

### 5.1 conversation.outbound

Published for each proactive message that should be delivered to a user. Consumed by the Channel Gateway / Channel Delivery Worker for outbound delivery.

**Topic**: `conversation.outbound`

```json
{
  "event_id": "evt-7002",
  "correlation_id": "evt-7001",
  "event_type": "conversation.reply.generated",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T01:00:15Z",
  "user_id": "usr_9f2a7c41",
  "channel": "telegram",
  "conversation_id": "telegram-chat-123456789",
  "responses": [
    {
      "type": "text",
      "content": "Hey Alice, just checking in—how has your week been so far?"
    }
  ],
  "metadata": {
    "source": "proactive_engagement",
    "days_inactive": 3,
    "affinity_score": 0.74,
    "tier": "close_friend"
  }
}
```

| Field             | Type   | Description                                    |
|-------------------|--------|------------------------------------------------|
| `event_id`        | string | Unique event identifier                        |
| `correlation_id`  | string | Correlation ID from the scan trigger           |
| `event_type`      | string | `conversation.reply.generated`                 |
| `schema_version`  | string | Schema version for forward compatibility       |
| `timestamp`       | string | ISO 8601 timestamp                             |
| `user_id`         | string | Internal user identifier                       |
| `channel`         | string | Delivery channel (e.g., `telegram`)            |
| `conversation_id` | string | Conversation identifier for routing            |
| `responses`       | array  | List of response items to deliver              |
| `metadata`        | object | Additional metadata about the proactive action |

---

### 5.2 proactive.dispatch.completed

Published after a proactive scan completes for telemetry and monitoring.

**Topic**: `proactive.dispatch.completed`

```json
{
  "event_id": "evt-7003",
  "correlation_id": "evt-7001",
  "event_type": "proactive.dispatch.completed",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T01:02:30Z",
  "stats": {
    "candidates_scanned": 500,
    "messages_dispatched": 127,
    "messages_skipped": 373
  }
}
```

| Field            | Type   | Description                                    |
|------------------|--------|------------------------------------------------|
| `event_id`       | string | Unique event identifier                        |
| `correlation_id` | string | Correlation ID from the scan trigger           |
| `event_type`     | string | Always `proactive.dispatch.completed`          |
| `schema_version` | string | Schema version for forward compatibility       |
| `timestamp`      | string | ISO 8601 timestamp of completion               |
| `stats`          | object | Dispatch statistics                            |

---

## 6. Error Handling

### HTTP Status Codes

| Status | Meaning                                                |
|--------|--------------------------------------------------------|
| 200    | Success                                                |
| 422    | Validation error — request body failed schema validation |
| 500    | Internal error — unexpected failure during scan        |

### Error Response Format

```json
{
  "error": "INTERNAL_ERROR",
  "message": "Descriptive error message."
}
```

---

## 7. Data Models

### DispatchResult

```json
{
  "user_id": "usr_9f2a7c41",
  "dispatched": true,
  "skip_reason": null
}
```

### CandidateSearchFilters

```json
{
  "min_days_inactive": 3,
  "min_affinity_score": 0.5,
  "max_batch_size": 500
}
```

### OutboundResponseItem

```json
{
  "type": "text",
  "content": "Hey Alice, just checking in—how has your week been so far?"
}
```

---

## 8. Pipeline Flow

The following diagram illustrates the proactive engagement pipeline:

```
┌──────────────────┐     ┌──────────────────────────────────────┐
│ Platform Scheduler│────▶│ proactive.scan.requested (Event)     │
└──────────────────┘     └──────────────┬───────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │ Proactive Engagement Service  │
                         │                              │
                         │  1. Search candidates        │◄──── Relationship Service
                         │  2. Check eligibility        │◄──── User Profile Service
                         │  3. Retrieve memory summary  │◄──── Memory Service
                         │  4. Generate proactive msg   │◄──── AI Generation Service
                         │  5. Publish outbound event   │
                         └──────────┬───────────────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     ▼                             ▼
        ┌────────────────────┐     ┌──────────────────────────┐
        │ conversation.       │     │ proactive.dispatch.       │
        │ outbound (Event)    │     │ completed (Event)         │
        └────────┬───────────┘     └──────────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │ Channel Gateway /   │
        │ Delivery Worker     │
        └────────────────────┘
```
