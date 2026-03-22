# AI Generation Service — API Interface Reference

**Version**: 1.0  
**Last Updated**: 2026-03-23  
**Maintained by**: AI Generation Service Team

---

## Table of Contents

1. [Service Overview](#1-service-overview)
2. [Access Information](#2-access-information)
3. [API Endpoints](#3-api-endpoints)
   - [POST /api/v1/generation/chat-completions](#31-post-apiv1generationchat-completions)
   - [POST /api/v1/generation/summaries](#32-post-apiv1generationsummaries)
   - [POST /api/v1/generation/proactive-messages](#33-post-apiv1generationproactive-messages)
   - [GET /health](#34-get-health)
   - [GET /ready](#35-get-ready)
4. [Published Events](#4-published-events)
   - [ai.generation.failed](#41-aigenerationfailed)
   - [ai.generation.completed](#42-aigenerationcompleted)
5. [Error Handling](#5-error-handling)
6. [Data Models](#6-data-models)

---

## 1. Service Overview

The AI Generation Service provides model-agnostic text generation capabilities for the ECHO platform. It encapsulates all interactions with foundation models (currently Amazon Bedrock / Claude) and exposes a clean internal API for three generation use cases: conversational reply generation, memory summarization, and proactive outreach message drafting.

The service implements retry logic with exponential backoff and optional fallback to a secondary provider. It publishes telemetry events for monitoring and failure events for incident workflows.

**Responsibilities**:

- Handle provider-agnostic chat completion requests
- Apply provider-specific request transformation and model request shaping
- Generate summarization outputs for memory compaction workflows
- Generate proactive outreach message drafts when requested
- Apply model fallback and timeout retry policies
- Return usage and generation metadata for observability and governance

---

## 2. Access Information

**Base URL** (internal network):

```
http://<host>:8003
```

| Port | Purpose                              |
|------|--------------------------------------|
| 8003 | AI Generation Service main API       |

**Protocol**: HTTP/1.1, JSON request and response bodies, `Content-Type: application/json`.

**Interactive Docs**: `http://<host>:8003/docs` (Swagger UI)

---

## 3. API Endpoints

### 3.1 POST /api/v1/generation/chat-completions

Generate a conversational reply from a message list including a system prompt.

**Source**: Conversation Orchestrator Service  
**Type**: Internal synchronous API call

**Request body**:

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "messages": [
    {
      "role": "system",
      "content": "You are ECHO, a warm and concise companion."
    },
    {
      "role": "user",
      "content": "Hello ECHO"
    }
  ],
  "generation_config": {
    "temperature": 0.7,
    "max_tokens": 200,
    "top_p": null,
    "stop_sequences": null
  },
  "correlation_id": "evt-001"
}
```

| Field              | Type   | Required | Description                                      |
|--------------------|--------|----------|--------------------------------------------------|
| `user_id`          | string | yes      | Internal user identifier                         |
| `conversation_id`  | string | yes      | Conversation identifier                          |
| `messages`         | array  | yes      | Ordered message list (system + user + assistant)  |
| `generation_config`| object | no       | Optional generation hyperparameters              |
| `correlation_id`   | string | no       | Correlation ID for distributed tracing           |

**`generation_config` fields**:

| Field            | Type    | Default | Description                          |
|------------------|---------|---------|--------------------------------------|
| `temperature`    | float   | 0.7     | Sampling temperature (0.0–2.0)       |
| `max_tokens`     | integer | 512     | Maximum tokens to generate (1–4096)  |
| `top_p`          | float   | null    | Nucleus sampling parameter (0.0–1.0) |
| `stop_sequences` | array   | null    | Sequences that stop generation       |

**Response** `200 OK`:

```json
{
  "response_id": "gen-445",
  "output": [
    {
      "type": "text",
      "content": "Hey Alice, nice to hear from you."
    }
  ],
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 812,
    "output_tokens": 39
  }
}
```

| Field         | Type   | Description                              |
|---------------|--------|------------------------------------------|
| `response_id` | string | Unique generation response identifier    |
| `output`      | array  | List of output segments (type + content) |
| `model`       | string | Model identifier used for generation     |
| `usage`       | object | Token usage statistics                   |

---

### 3.2 POST /api/v1/generation/summaries

Generate a compact summary from a conversation message window for memory compaction.

**Source**: Memory Service  
**Type**: Internal synchronous API call

**Request body**:

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "messages_window": {
    "from_message_id": "msg-601",
    "to_message_id": "msg-645"
  },
  "summary_type": "memory_compaction",
  "correlation_id": "evt-022"
}
```

| Field             | Type   | Required | Description                                    |
|-------------------|--------|----------|------------------------------------------------|
| `user_id`         | string | yes      | Internal user identifier                       |
| `conversation_id` | string | yes      | Conversation identifier                        |
| `messages_window` | object | yes      | Message ID range to summarize                  |
| `summary_type`    | string | yes      | Summary type (e.g., `memory_compaction`)        |
| `correlation_id`  | string | no       | Correlation ID for distributed tracing         |

**Response** `200 OK`:

```json
{
  "content": "User values supportive check-ins and tends to exercise in the evening.",
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 1220,
    "output_tokens": 57
  }
}
```

| Field     | Type   | Description                          |
|-----------|--------|--------------------------------------|
| `content` | string | Generated summary text               |
| `model`   | string | Model identifier used for generation |
| `usage`   | object | Token usage statistics               |

> **Note**: This endpoint internally calls the Conversation Persistence Store to retrieve the actual messages within the specified window. See [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md) for the assumed store API.

---

### 3.3 POST /api/v1/generation/proactive-messages

Generate a personalized proactive outreach message for re-engagement.

**Source**: Proactive Engagement Service  
**Type**: Internal synchronous API call

**Request body**:

```json
{
  "user_id": "usr_9f2a7c41",
  "relationship": {
    "tier": "close_friend",
    "affinity_score": 0.74,
    "days_inactive": 3
  },
  "context": {
    "recent_summary": "User enjoys evening workouts and friendly check-ins",
    "timezone": "Asia/Singapore"
  },
  "constraints": {
    "max_tokens": 120,
    "tone": "friendly"
  },
  "correlation_id": "evt-6001"
}
```

| Field            | Type   | Required | Description                                |
|------------------|--------|----------|--------------------------------------------|
| `user_id`        | string | yes      | Internal user identifier                   |
| `relationship`   | object | yes      | Current relationship state                 |
| `context`        | object | no       | Contextual info for personalization        |
| `constraints`    | object | no       | Generation constraints (tokens, tone)      |
| `correlation_id` | string | no       | Correlation ID for distributed tracing     |

**`relationship` fields**:

| Field           | Type   | Description                                     |
|-----------------|--------|-------------------------------------------------|
| `tier`          | string | acquaintance, friend, close_friend, best_friend |
| `affinity_score`| float  | 0.0–1.0 affinity score                          |
| `days_inactive` | int    | Days since last user interaction                 |

**`context` fields**:

| Field           | Type   | Description                          |
|-----------------|--------|--------------------------------------|
| `recent_summary`| string | Recent memory summary for the user   |
| `timezone`      | string | User timezone (IANA format)          |

**`constraints` fields**:

| Field       | Type   | Default    | Description                      |
|-------------|--------|------------|----------------------------------|
| `max_tokens`| int    | 120        | Maximum tokens for the message   |
| `tone`      | string | "friendly" | Desired tone of the message      |

**Response** `200 OK`:

```json
{
  "response_id": "gen-980",
  "output": [
    {
      "type": "text",
      "content": "Hey Alice, just checking in—how has your week been so far?"
    }
  ],
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 532,
    "output_tokens": 26
  }
}
```

---

### 3.4 GET /health

Basic liveness check.

**Response** `200 OK`:

```json
{
  "status": "healthy",
  "service": "ai-generation-service"
}
```

---

### 3.5 GET /ready

Readiness check verifying the service can accept requests.

**Response** `200 OK`:

```json
{
  "status": "ready",
  "service": "ai-generation-service"
}
```

---

## 4. Published Events

The AI Generation Service publishes the following events to the Internal Asynchronous Messaging Layer for monitoring and telemetry purposes.

### 4.1 ai.generation.failed

Published when a generation request fails after all retry and fallback attempts.

**Topic**: `ai.generation.failed`

```json
{
  "event_id": "evt-6002",
  "correlation_id": "evt-001",
  "event_type": "ai.generation.failed",
  "schema_version": "1.0",
  "timestamp": "2026-03-11T15:10:03Z",
  "user_id": "usr_9f2a7c41",
  "operation": "chat_completion",
  "error_code": "PROVIDER_TIMEOUT",
  "retryable": true,
  "fallback_attempted": true
}
```

| Field               | Type    | Description                                                |
|---------------------|---------|------------------------------------------------------------|
| `event_id`          | string  | Unique event identifier                                    |
| `correlation_id`    | string  | Correlation ID from the original request                   |
| `event_type`        | string  | Always `ai.generation.failed`                              |
| `schema_version`    | string  | Schema version for forward compatibility                   |
| `timestamp`         | string  | ISO 8601 timestamp of the failure                          |
| `user_id`           | string  | Internal user identifier                                   |
| `operation`         | string  | `chat_completion`, `summary_generation`, or `proactive_message` |
| `error_code`        | string  | `PROVIDER_TIMEOUT`, `PROVIDER_ERROR`, `CONVERSATION_STORE_UNAVAILABLE` |
| `retryable`         | boolean | Whether the failure is retryable                           |
| `fallback_attempted`| boolean | Whether a fallback provider was attempted                  |

---

### 4.2 ai.generation.completed

Published for telemetry, monitoring, and audit trails only. This is NOT a second business response path.

**Topic**: `ai.generation.completed`

```json
{
  "event_id": "evt-6003",
  "correlation_id": "evt-022",
  "event_type": "ai.generation.completed",
  "schema_version": "1.0",
  "timestamp": "2026-03-11T15:10:06Z",
  "user_id": "usr_9f2a7c41",
  "operation": "summary_generation",
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 1220,
    "output_tokens": 57
  }
}
```

| Field            | Type   | Description                                                |
|------------------|--------|------------------------------------------------------------|
| `event_id`       | string | Unique event identifier                                    |
| `correlation_id` | string | Correlation ID from the original request                   |
| `event_type`     | string | Always `ai.generation.completed`                           |
| `schema_version` | string | Schema version for forward compatibility                   |
| `timestamp`      | string | ISO 8601 timestamp of completion                           |
| `user_id`        | string | Internal user identifier                                   |
| `operation`      | string | `chat_completion`, `summary_generation`, or `proactive_message` |
| `model`          | string | Model identifier used                                      |
| `usage`          | object | Token usage: `{input_tokens, output_tokens}`               |

---

## 5. Error Handling

### HTTP Status Codes

| Status | Meaning                                                          |
|--------|------------------------------------------------------------------|
| 200    | Success                                                          |
| 422    | Validation error — request body failed schema validation         |
| 500    | Internal error — non-retryable provider or system failure        |
| 503    | Service unavailable — retryable provider failure (timeout, etc.) |

### Error Response Format

```json
{
  "error_code": "PROVIDER_TIMEOUT",
  "message": "AI provider did not respond within the configured timeout.",
  "retryable": true,
  "correlation_id": "evt-001"
}
```

### Error Codes

| Code                             | Retryable | Description                                    |
|----------------------------------|-----------|------------------------------------------------|
| `PROVIDER_TIMEOUT`               | yes       | AI provider did not respond in time            |
| `PROVIDER_ERROR`                 | no        | AI provider returned an unrecoverable error    |
| `CONVERSATION_STORE_UNAVAILABLE` | yes       | Failed to retrieve messages for summarization  |
| `INTERNAL_ERROR`                 | no        | Unexpected internal error                      |

---

## 6. Data Models

### MessageItem

```json
{
  "role": "user",
  "content": "Hello ECHO"
}
```

| Field   | Type   | Description                               |
|---------|--------|-------------------------------------------|
| `role`  | string | `system`, `user`, or `assistant`          |
| `content`| string | Text content of the message              |

### OutputItem

```json
{
  "type": "text",
  "content": "Hey Alice, nice to hear from you."
}
```

| Field    | Type   | Description                    |
|----------|--------|--------------------------------|
| `type`   | string | Output type (currently `text`) |
| `content`| string | Generated text content         |

### UsageInfo

```json
{
  "input_tokens": 812,
  "output_tokens": 39
}
```

| Field          | Type | Description                      |
|----------------|------|----------------------------------|
| `input_tokens` | int  | Number of input tokens consumed  |
| `output_tokens`| int  | Number of output tokens generated|
