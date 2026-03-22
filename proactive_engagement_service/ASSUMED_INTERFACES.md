# Proactive Engagement Service — Assumed External Interfaces

**Version**: 1.0  
**Last Updated**: 2026-03-23  
**Status**: TO BE UPDATED — These interfaces are assumed based on the architecture specification and have not been confirmed with the owning teams.

---

## Purpose

This document lists all external service interfaces that the Proactive Engagement Service depends on but that are not yet formally defined or deployed. Each entry describes the assumed contract so that integration can proceed. Once the owning service publishes its official API, the corresponding assumption should be verified and this document updated accordingly.

---

## 1. Relationship Service — Proactive Candidate Search

**Owner**: Relationship Service Team  
**Status**: TO BE UPDATED

The Proactive Engagement Service calls this endpoint to search for users who are candidates for proactive outreach based on inactivity and affinity score thresholds.

**Assumed Endpoint**:

```
POST /api/v1/relationships/proactive-candidates/search
```

**Assumed Base URL**: Configured via `PROACTIVE_RELATIONSHIP_SERVICE_BASE_URL` environment variable.

**Assumed Request**:

```json
{
  "filters": {
    "min_days_inactive": 3,
    "min_affinity_score": 0.5,
    "max_batch_size": 500
  },
  "time_context": {
    "timezone": "Asia/Singapore",
    "current_time": "2026-03-12T09:00:00+08:00"
  },
  "correlation_id": "evt-7001"
}
```

| Field            | Type   | Required | Description                          |
|------------------|--------|----------|--------------------------------------|
| `filters`        | object | yes      | Candidate selection filters          |
| `time_context`   | object | yes      | Time context for the scan            |
| `correlation_id` | string | no       | Correlation ID for tracing           |

**Assumed Response** `200 OK`:

```json
{
  "candidates": [
    {
      "user_id": "usr_9f2a7c41",
      "days_inactive": 3,
      "affinity_score": 0.74
    },
    {
      "user_id": "usr_b3d8e012",
      "days_inactive": 5,
      "affinity_score": 0.62
    }
  ]
}
```

**Notes**:

- Candidates should be returned sorted by affinity score descending.
- The Relationship Service is responsible for enforcing the `max_batch_size` limit.
- The `time_context` allows the Relationship Service to factor in timezone-aware inactivity calculations.

---

## 2. Relationship Service — User Relationship Context

**Owner**: Relationship Service Team  
**Status**: TO BE UPDATED

Used to retrieve detailed relationship context for a specific user when needed for enrichment.

**Assumed Endpoint**:

```
GET /api/v1/relationships/{user_id}/context
```

**Assumed Response** `200 OK`:

```json
{
  "user_id": "usr_9f2a7c41",
  "tier": "close_friend",
  "affinity_score": 0.74,
  "days_inactive": 3,
  "last_interaction": "2026-03-09T14:30:00Z",
  "interaction_count": 145
}
```

**Notes**:

- Returns 404 if no relationship data exists for the user.
- This endpoint is used for individual enrichment, not batch operations.

---

## 3. User Profile Service — User Profile Retrieval

**Owner**: User Profile Service Team  
**Status**: TO BE UPDATED

The Proactive Engagement Service calls this endpoint to retrieve user consent flags, quiet hours preferences, timezone, and channel information for eligibility checking and outbound delivery routing.

**Assumed Endpoint**:

```
GET /api/v1/users/{user_id}/profile
```

**Assumed Base URL**: Configured via `PROACTIVE_USER_PROFILE_SERVICE_BASE_URL` environment variable.

**Assumed Response** `200 OK`:

```json
{
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "channel": "telegram",
  "timezone": "Asia/Singapore",
  "consent": {
    "data_collection": true,
    "proactive_messaging": true,
    "memory_storage": true
  },
  "preferences": {
    "quiet_hours": {
      "start": "22:00",
      "end": "07:00"
    },
    "language": "en"
  }
}
```

**Fields used by this service**:

| Field                           | Usage                                      |
|---------------------------------|--------------------------------------------|
| `consent.proactive_messaging`   | Eligibility check — consent gate           |
| `preferences.quiet_hours.start` | Eligibility check — quiet hours gate       |
| `preferences.quiet_hours.end`   | Eligibility check — quiet hours gate       |
| `timezone`                      | Quiet hours calculation and personalization |
| `channel`                       | Outbound delivery routing                  |
| `external_user_id`              | Conversation ID derivation                 |

**Notes**:

- Returns 404 if the user profile does not exist.
- The `external_user_id` format is `{channel}:{platform_user_id}`.
- Conversation ID is derived as `{channel}-chat-{platform_user_id}`. This derivation convention is assumed and may need to be updated.

---

## 4. AI Generation Service — Proactive Message Generation

**Owner**: AI Generation Service Team  
**Status**: Defined (see `ai_generation_service/API_INTERFACES.md`)

The Proactive Engagement Service calls the AI Generation Service to request AI-generated proactive outreach messages.

**Primary Endpoint (v2.0 — recommended)**:

```
POST /api/v1/generation/execute
```

Using `template_id: "tpl_proactive_outreach"` with the `context_block` variable assembled by the Proactive Engagement Service.

**Legacy Endpoint (deprecated)**:

```
POST /api/v1/generation/proactive-messages
```

**Base URL**: Configured via `PROACTIVE_AI_GENERATION_SERVICE_BASE_URL` environment variable.

**Request and response schemas**: See [AI Generation Service API_INTERFACES.md](../ai_generation_service/API_INTERFACES.md).

**Notes**:

- This is the only dependency that is formally defined within this project.
- The AI Generation Service may return 503 (retryable) or 500 (non-retryable) errors.
- On failure, the candidate is marked as `generation_failed` and skipped.
- The Proactive Engagement Service is responsible for assembling the `context_block` variable from relationship data, user profile, and memory summaries.

---

## 5. Memory Service (MyMem0) — Semantic Memory Search

**Owner**: Memory Service Team  
**Status**: TO BE UPDATED

The Proactive Engagement Service calls this endpoint to retrieve recent memory summaries for personalizing proactive outreach messages.

**Assumed Endpoint**:

```
POST /search
```

**Assumed Base URL**: Configured via `PROACTIVE_MEMORY_SERVICE_BASE_URL` environment variable (default: `http://localhost:18088`).

**Assumed Request**:

```json
{
  "query": "recent activities and preferences",
  "user_id": "usr_9f2a7c41",
  "limit": 5,
  "threshold": 0.3
}
```

| Field      | Type    | Required | Description                                |
|------------|---------|----------|--------------------------------------------|
| `query`    | string  | yes      | Semantic search query                      |
| `user_id`  | string  | yes      | Internal user identifier                   |
| `limit`    | integer | no       | Maximum number of results (default: 5)     |
| `threshold`| float   | no       | Minimum similarity threshold (default: 0.3)|

**Assumed Response** `200 OK`:

```json
{
  "results": [
    {
      "id": "mem-001",
      "memory": "User enjoys evening workouts and friendly check-ins",
      "score": 0.85,
      "created_at": "2026-03-10T14:00:00Z"
    },
    {
      "id": "mem-002",
      "memory": "User prefers casual conversation tone",
      "score": 0.72,
      "created_at": "2026-03-09T10:00:00Z"
    }
  ]
}
```

**Notes**:

- Memory retrieval is best-effort. If the Memory Service is unavailable or returns no results, the proactive message is generated without personalization context.
- The `memory` field from each result is concatenated with semicolons to form the `recent_summary` passed to the AI Generation Service.
- This interface is based on the MyMem0 integration guide's `/search` endpoint.

---

## 6. Internal Asynchronous Messaging Layer — Event Consumption and Publishing

**Owner**: Platform / Infrastructure Team  
**Status**: TO BE UPDATED

The Proactive Engagement Service both consumes and publishes events via the Internal Asynchronous Messaging Layer.

### 6.1 Consumed Topics

| Topic                       | Description                                    |
|-----------------------------|------------------------------------------------|
| `proactive.scan.requested`  | Scan trigger from platform scheduler           |

### 6.2 Published Topics

| Topic                          | Description                                 |
|--------------------------------|---------------------------------------------|
| `conversation.outbound`        | Proactive messages for channel delivery     |
| `proactive.dispatch.completed` | Telemetry event after scan completion       |

**Assumed Broker Interface**: Same as described in the AI Generation Service's ASSUMED_INTERFACES.md. The concrete broker technology has not been finalized.

**Configuration**: Broker URL is configured via `PROACTIVE_EVENT_BROKER_URL` environment variable.

---

## 7. Platform Scheduler — Scan Trigger

**Owner**: Platform / Infrastructure Team  
**Status**: TO BE UPDATED

The platform scheduler is responsible for publishing `proactive.scan.requested` events at configured intervals (e.g., daily at 9:00 AM in each target timezone).

**Assumed Behavior**:

- The scheduler publishes one event per timezone window per day.
- The event includes a `window` object with `timezone` and `hour` fields.
- The scheduler does not manage candidate selection or dispatch — it only triggers the scan.

**Notes**:

- The scheduler implementation is outside the scope of this service.
- For testing, use the `POST /api/v1/proactive/trigger` endpoint to simulate scan triggers.

---

## Revision History

| Date       | Change                                    |
|------------|-------------------------------------------|
| 2026-03-23 | Initial assumed interfaces documented     |
