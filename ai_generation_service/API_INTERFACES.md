# AI Generation Service — API Interface Reference

> **Version**: 2.2.0
> **Last Updated**: 2026-03-24
> **Maintained by**: AI Generation Service Team  
> **Architecture Role**: AI Execution Engine + Prompt Template Management

---

## Table of Contents

1. [Service Overview](#1-service-overview)
2. [Access Information](#2-access-information)
3. [Template Management APIs](#3-template-management-apis)
4. [Generation APIs](#4-generation-apis)
   - [4.2 Embedding API](#42-post-apiv1generationembeddings--generate-embedding)
   - [4.5 Migration Guide](#45-migration-guide-legacy-endpoints--execute)
5. [Health and Readiness](#5-health-and-readiness)
6. [Published Events](#6-published-events)
7. [Error Handling](#7-error-handling)
8. [Data Models](#8-data-models)

---

## 1. Service Overview

The AI Generation Service is a **pure AI execution engine** with **prompt template management**. It does NOT contain business logic or prompt construction. Instead:

- **Business callers** assemble core prompt content (variables, conversation messages).
- **AI Service** manages prompt templates (system-level prompts, variable schemas, default parameters).
- **AI Service** renders templates with caller-supplied variables and executes them against AI providers.
- **AI Service** handles retry with exponential backoff, provider fallback, and telemetry event publishing.

The parameter resolution priority chain is: **Caller Config > Template Defaults > Service Defaults**.

**Responsibilities**:

- Manage the lifecycle of prompt templates (register, query, update).
- Render templates with caller-supplied variables into provider-ready prompts.
- Execute rendered prompts against AI providers (Amazon Bedrock / Claude primary, OpenAI-compatible fallback).
- Apply retry and fallback policies transparently.
- Publish telemetry and failure events for monitoring.

---

## 2. Access Information

**Base URL** (internal network):

```
http://<host>:8003
```

| Port | Purpose |
|------|---------|
| 8003 | AI Generation Service main API |

**Protocol**: HTTP/1.1, JSON request and response bodies, `Content-Type: application/json`.

**Interactive Docs**: `http://<host>:8003/docs` (Swagger UI)

---

## 3. Template Management APIs

### 3.1 POST /api/v1/templates — Register a New Template

Business callers register a new prompt template. The AI service assigns a unique `template_id` and returns it along with the variable schema so the caller knows exactly what to provide at generation time.

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable template name |
| `description` | string | No | Detailed description of the template's purpose |
| `owner` | string | Yes | Service or team registering this template |
| `category` | string | No | Template category (e.g., `chat`, `summarization`, `proactive`, `analysis`, `safety`) |
| `system_prompt` | string | Yes | The system-level prompt for this template |
| `user_prompt_template` | string | Yes | User prompt template with `{{variable}}` placeholders |
| `variables` | object | No | Schema of variables accepted by this template (see TemplateVariableSchema) |
| `defaults` | object | No | Default generation parameters (see TemplateDefaults) |
| `tags` | array | No | Tags for search and filtering |

**Request Example**:

```json
{
  "name": "Custom Greeting",
  "owner": "conversation-orchestrator",
  "category": "chat",
  "system_prompt": "You are ECHO, a friendly companion.",
  "user_prompt_template": "Greet the user based on context:\n{{context}}\n\nGenerate a warm greeting.",
  "variables": {
    "context": {
      "type": "string",
      "required": true,
      "description": "User context for personalized greeting."
    }
  },
  "defaults": {
    "temperature": 0.8,
    "max_tokens": 100
  },
  "tags": ["chat", "greeting"]
}
```

**Response** `201 Created`:

```json
{
  "template_id": "tpl_custom_greeting_a1b2c3",
  "name": "Custom Greeting",
  "version": "1.0.0",
  "variables": {
    "context": {
      "type": "string",
      "required": true,
      "default": null,
      "description": "User context for personalized greeting."
    }
  },
  "defaults": {
    "temperature": 0.8,
    "max_tokens": 100,
    "top_p": null,
    "stop_sequences": null
  },
  "message": "Template registered successfully."
}
```

**Error** `409 Conflict`: A template with the same name and owner already exists.

---

### 3.2 GET /api/v1/templates — List Templates

Returns all registered templates with optional filtering.

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by category |
| `owner` | string | Filter by owner |
| `tag` | string | Filter by tag |

**Response** `200 OK`:

```json
{
  "templates": [
    {
      "template_id": "tpl_chat_completion",
      "name": "Chat Completion",
      "description": "Default system-level wrapper for multi-turn chat completion.",
      "version": "1.0.0",
      "owner": "ai-generation-service",
      "category": "chat",
      "tags": ["chat", "multi-turn", "default"],
      "updated_at": "2026-03-23T00:00:00Z"
    }
  ],
  "total": 6
}
```

---

### 3.3 GET /api/v1/templates/{template_id} — Get Template by ID

Returns the full template definition including system prompt, user prompt template, variable schema, and default parameters.

**Response** `200 OK`: Full `PromptTemplate` object (see [Data Models](#8-data-models)).

**Response** `404 Not Found`: Template not found.

---

### 3.4 PUT /api/v1/templates/{template_id} — Update a Template

Update an existing template. Only the provided fields are updated. The version is bumped automatically by the AI service.

**Request Body** (all fields optional):

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Updated template name |
| `description` | string | Updated description |
| `system_prompt` | string | Updated system prompt |
| `user_prompt_template` | string | Updated user prompt template |
| `variables` | object | Updated variable schema |
| `defaults` | object | Updated default generation parameters |
| `tags` | array | Updated tags |

**Response** `200 OK`: Full updated `PromptTemplate` object.

**Response** `404 Not Found`: Template not found.

---

## 4. Generation APIs

### 4.1 POST /api/v1/generation/execute — Execute Generation (Primary)

The **primary** generation endpoint. Business callers specify a `template_id` and provide variables (or messages for multi-turn chat). The AI service renders the prompt from the template and executes it.

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | Internal user identifier |
| `conversation_id` | string | No | Conversation identifier for context tracking |
| `template_id` | string | Yes | The prompt template ID to use |
| `variables` | object | No | Variable values to substitute into the template |
| `messages` | array | No | Conversation message list for multi-turn chat templates |
| `generation_config` | object | No | Override generation parameters |
| `correlation_id` | string | No | Correlation ID for distributed tracing |

**`generation_config` fields**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `temperature` | float | (template default) | Sampling temperature (0.0-2.0) |
| `max_tokens` | integer | (template default) | Maximum tokens to generate (1-4096) |
| `top_p` | float | null | Nucleus sampling parameter (0.0-1.0) |
| `stop_sequences` | array | null | Sequences that stop generation |

**Invocation Patterns**:

All three core use cases (chat, summarization, proactive) use the same `user_prompt` variable. The caller assembles the full prompt; the AI service provides the system-level prompt via the template.

**Pattern A — Variable-based** (for summarization, proactive, analysis, etc.):

All preset templates accept a single `user_prompt` variable. The caller is responsible for assembling the full prompt content.

```json
{
  "user_id": "usr_9f2a7c41",
  "template_id": "tpl_proactive_outreach",
  "variables": {
    "user_prompt": "Based on the following context, compose a short, natural check-in message to re-engage this user.\n\nRelationship tier: close_friend\nAffinity score: 0.74\nDays inactive: 3\nTone: warm\nRecent context: User enjoys evening workouts\n\nGenerate only the message text, nothing else."
  },
  "correlation_id": "evt-6001"
}
```

```json
{
  "user_id": "usr_9f2a7c41",
  "template_id": "tpl_memory_compaction",
  "variables": {
    "user_prompt": "Please summarize the following conversation into a compact memory entry.\nSummary type: memory_compaction\n\nConversation:\n[user]: I went for a run this evening.\n[assistant]: That's great! How did it go?\n\nProvide a concise summary capturing the user's key preferences, emotional state, and important facts."
  },
  "correlation_id": "evt-022"
}
```

**Pattern B — Message-based** (for multi-turn chat):

For `tpl_chat_completion`, callers can also pass a full conversation history via `messages` instead of `variables`. The template's system prompt is merged with the caller's message list.

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "template_id": "tpl_chat_completion",
  "messages": [
    {"role": "system", "content": "You are ECHO, a warm companion. The user likes hiking."},
    {"role": "user", "content": "Hey ECHO, any trail suggestions?"},
    {"role": "assistant", "content": "Sure! What difficulty level are you looking for?"},
    {"role": "user", "content": "Something moderate, about 2 hours."}
  ],
  "generation_config": {
    "temperature": 0.7,
    "max_tokens": 300
  }
}
```

**Response** `200 OK`:

```json
{
  "response_id": "gen-a1b2c3d4e5f6",
  "template_id": "tpl_proactive_outreach",
  "output": [
    {
      "type": "text",
      "content": "Hey! It's been a few days — hope your workouts are going well."
    }
  ],
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 156,
    "output_tokens": 32
  }
}
```

---

### 4.2 POST /api/v1/generation/embeddings — Generate Embedding

Generate a dense vector embedding for the given input text. Uses the configured embedding model (Amazon Titan Embeddings v2 by default) via the same provider infrastructure as `/execute` (retry + fallback).

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | Internal user identifier |
| `input` | string | Yes | The text to generate an embedding for (min 1 character) |
| `correlation_id` | string | No | Correlation ID for distributed tracing |

**Request Example**:

```json
{
  "user_id": "usr_9f2a7c41",
  "input": "User enjoys evening workouts and friendly check-ins.",
  "correlation_id": "evt-emb-001"
}
```

**Response** `200 OK`:

```json
{
  "response_id": "gen-a1b2c3d4e5f6",
  "embedding": [0.0123, -0.0456, 0.0789, ...],
  "dimension": 1024,
  "model": "amazon.titan-embed-text-v2:0",
  "usage": {
    "input_tokens": 12,
    "output_tokens": 0
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `response_id` | string | Unique identifier for this response |
| `embedding` | array of float | The embedding vector |
| `dimension` | integer | Dimensionality of the embedding vector |
| `model` | string | Model identifier used for embedding |
| `usage` | UsageInfo | Token usage (`output_tokens` is always 0 for embeddings) |

**Errors**: Same error codes as `/execute` (`PROVIDER_TIMEOUT` 503, `PROVIDER_ERROR` 500, `INTERNAL_ERROR` 500).

**Configuration**: The embedding model is configured via `AI_GEN_BEDROCK_EMBEDDING_MODEL_ID` (default: `amazon.titan-embed-text-v2:0`).

---

### 4.3 Active Legacy: POST /api/v1/generation/chat-completions

> **Status**: ✅ Implemented and actively called by **Channel Gateway Orchestrator** (`ai_generation_client.py`). Maintain until Orchestrator migrates to `/execute`.

Accepts a conversation message list and returns an AI-generated reply. If `template_id` is omitted, uses `tpl_chat_completion`.

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | Internal user identifier |
| `conversation_id` | string | Yes | Conversation identifier |
| `messages` | array of `MessageItem` | Yes | Ordered conversation messages (min 1) |
| `template_id` | string | No | Template ID to use (default: `tpl_chat_completion`) |
| `generation_config` | GenerationConfig | No | Override generation parameters |
| `correlation_id` | string | No | Correlation ID for tracing |

**Request Example**:

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "messages": [
    {"role": "system", "content": "You are ECHO, a warm companion."},
    {"role": "user", "content": "Hey ECHO!"}
  ],
  "generation_config": {
    "temperature": 0.7,
    "max_tokens": 200
  },
  "correlation_id": "evt-001"
}
```

**Response** `200 OK`:

```json
{
  "response_id": "gen-445",
  "output": [
    {"type": "text", "content": "Hey! Great to hear from you."}
  ],
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 156,
    "output_tokens": 22
  }
}
```

---

### 4.4 Inactive Legacy Endpoints (No Active Callers)

> **Status**: ⚠️ Code implemented but **no service in the codebase currently calls these endpoints**. Candidates for removal in a future cleanup pass once confirmed that no planned callers exist.

#### POST /api/v1/generation/summaries

Accepts a message window reference and generates a compact summary. If `template_id` is omitted, uses `tpl_memory_compaction`. This endpoint depends on the Conversation Persistence Store (assumed interface, see [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md)).

#### POST /api/v1/generation/proactive-messages

Accepts relationship context and generates a personalized check-in message. If `template_id` is omitted, uses `tpl_proactive_outreach`.

> **Note**: The `usage` field in the proactive message response is optional and may be `null`.

> See the Swagger UI at `/docs` for detailed request/response schemas for these endpoints.

---

### 4.5 Migration Guide: Legacy Endpoints → `/execute`

This section helps business teams migrate from the legacy endpoints (defined in the architecture draft) to the unified `/execute` endpoint. For each use case, the **Before** shows the old calling convention and the **After** shows the new one.

#### Use Case A: Chat Completion (Conversation Orchestrator)

**Before** — `POST /api/v1/generation/chat-completions`:

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "messages": [
    {"role": "system", "content": "You are ECHO, a warm companion."},
    {"role": "user", "content": "Hey ECHO, any trail suggestions?"},
    {"role": "assistant", "content": "Sure! What difficulty level?"},
    {"role": "user", "content": "Something moderate, about 2 hours."}
  ],
  "generation_config": {
    "temperature": 0.7,
    "max_tokens": 200
  },
  "correlation_id": "evt-001"
}
```

**After** — `POST /api/v1/generation/execute`:

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "template_id": "tpl_chat_completion",
  "messages": [
    {"role": "system", "content": "You are ECHO, a warm companion."},
    {"role": "user", "content": "Hey ECHO, any trail suggestions?"},
    {"role": "assistant", "content": "Sure! What difficulty level?"},
    {"role": "user", "content": "Something moderate, about 2 hours."}
  ],
  "generation_config": {
    "temperature": 0.7,
    "max_tokens": 200
  },
  "correlation_id": "evt-001"
}
```

**What changes**:

| Item | Before | After |
|------|--------|-------|
| Endpoint | `POST /api/v1/generation/chat-completions` | `POST /api/v1/generation/execute` |
| New required field | — | `"template_id": "tpl_chat_completion"` |
| `messages` field | Same | Same (no change) |
| `generation_config` | Same | Same (no change) |
| Response body | `{response_id, output, model, usage}` | `{response_id, template_id, output, model, usage}` (adds `template_id`) |

> **Migration effort**: Minimal. Change the endpoint URL, add `template_id`, handle the extra `template_id` field in the response (or ignore it).

---

#### Use Case B: Memory Compaction Summary (Memory Service)

**Before** — `POST /api/v1/generation/summaries` (architecture draft):

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

The old endpoint would internally fetch conversation messages from the Conversation Persistence Store and assemble the prompt.

**After** — `POST /api/v1/generation/execute`:

```json
{
  "user_id": "usr_9f2a7c41",
  "template_id": "tpl_memory_compaction",
  "variables": {
    "user_prompt": "Please summarize the following conversation into a compact memory entry.\nSummary type: memory_compaction\n\nConversation:\n[user]: I went for a run this evening.\n[assistant]: That's great! How did it go?\n[user]: It was good, I ran 5km in the park.\n[assistant]: Nice! That's a solid distance.\n\nProvide a concise summary capturing the user's key preferences, emotional state, and important facts."
  },
  "generation_config": {
    "temperature": 0.3,
    "max_tokens": 300
  },
  "correlation_id": "evt-022"
}
```

**What changes**:

| Item | Before | After |
|------|--------|-------|
| Endpoint | `POST /api/v1/generation/summaries` | `POST /api/v1/generation/execute` |
| Message retrieval | AI service fetches messages via `messages_window` | **Caller fetches messages** and assembles them into `user_prompt` |
| `summary_type` | Dedicated field | Embedded in `user_prompt` text |
| `conversation_id` | Required | Optional (only needed for tracking) |
| New required field | — | `"template_id": "tpl_memory_compaction"` |
| Response body | `{content, model, usage}` | `{response_id, template_id, output[], model, usage}` — summary text is in `output[0].content` |

> **Migration effort**: Medium. The caller must now fetch conversation messages itself and assemble the full prompt. The `summary_type` and conversation text are concatenated into a single `user_prompt` string. The response format also changes — extract `output[0].content` instead of `content`.

---

#### Use Case C: Proactive Outreach Message (Proactive Engagement Service)

**Before** — `POST /api/v1/generation/proactive-messages` (architecture draft):

```json
{
  "user_id": "usr_9f2a7c41",
  "relationship": {
    "tier": "close_friend",
    "affinity_score": 0.74,
    "days_inactive": 3
  },
  "context": {
    "recent_summary": "User enjoys evening workouts",
    "timezone": "Asia/Singapore"
  },
  "constraints": {
    "max_tokens": 120,
    "tone": "warm"
  },
  "correlation_id": "evt-6001"
}
```

**After** — `POST /api/v1/generation/execute`:

```json
{
  "user_id": "usr_9f2a7c41",
  "template_id": "tpl_proactive_outreach",
  "variables": {
    "user_prompt": "Based on the following context, compose a short, natural check-in message to re-engage this user. The message should feel genuine and not automated.\n\nRelationship tier: close_friend\nAffinity score: 0.74\nDays since last interaction: 3\nDesired tone: warm\nUser timezone: Asia/Singapore\nRecent context about the user: User enjoys evening workouts\n\nGenerate only the message text, nothing else."
  },
  "generation_config": {
    "max_tokens": 120
  },
  "correlation_id": "evt-6001"
}
```

**What changes**:

| Item | Before | After |
|------|--------|-------|
| Endpoint | `POST /api/v1/generation/proactive-messages` | `POST /api/v1/generation/execute` |
| `relationship` (structured) | Dedicated object with `tier`, `affinity_score`, `days_inactive` | Flattened into `user_prompt` text |
| `context` (structured) | Dedicated object with `recent_summary`, `timezone` | Flattened into `user_prompt` text |
| `constraints.tone` | Dedicated field | Embedded in `user_prompt` text (e.g., "Desired tone: warm") |
| `constraints.max_tokens` | Inside `constraints` object | Moved to `generation_config.max_tokens` |
| New required field | — | `"template_id": "tpl_proactive_outreach"` |
| Response body | `{response_id, output, model, usage}` | `{response_id, template_id, output, model, usage}` (adds `template_id`) |

> **Migration effort**: Medium. The caller must flatten the structured `relationship`, `context`, and `constraints` fields into a single `user_prompt` string. The `max_tokens` constraint moves to `generation_config`. The caller gains full control over prompt wording, which allows more flexible personalization.

---

#### Response Format Comparison

All three use cases now return the same unified response format from `/execute`:

```json
{
  "response_id": "gen-a1b2c3d4e5f6",
  "template_id": "tpl_chat_completion",
  "output": [
    {"type": "text", "content": "Generated text here."}
  ],
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 156,
    "output_tokens": 32
  }
}
```

To extract the generated text: `response["output"][0]["content"]`.

---

## 5. Health and Readiness

### GET /health

Basic liveness check.

**Response** `200 OK`:

```json
{
  "status": "healthy",
  "service": "ai-generation-service",
  "version": "2.2.0"
}
```

### GET /ready

Readiness check verifying the service can accept requests.

> **Note**: 🔶 **Stub** — The readiness check currently does not verify provider connectivity. It always returns `ready`. See `routes/health_routes.py`.

**Response** `200 OK`:

```json
{
  "status": "ready",
  "service": "ai-generation-service"
}
```

---

## 6. Published Events

> **Implementation Status**: 🔶 **Stub** — The event schemas below are fully defined and events are serialized correctly in code. However, `EventPublisher._publish()` currently only logs events; no actual message broker is connected. Integration with a real broker (Redis Streams, RabbitMQ, etc.) is pending infrastructure decisions. See `events/publisher.py`.

The AI Generation Service publishes the following events to the Internal Asynchronous Messaging Layer.

### 6.1 ai.generation.completed

Published after every successful generation for telemetry and monitoring.

```json
{
  "event_id": "evt-a1b2c3d4e5f6",
  "event_type": "ai.generation.completed",
  "schema_version": "1.0",
  "timestamp": "2026-03-23T15:10:03Z",
  "user_id": "usr_9f2a7c41",
  "operation": "execute:tpl_proactive_outreach",
  "model": "claude-sonnet",
  "usage": {
    "input_tokens": 156,
    "output_tokens": 32
  },
  "correlation_id": "evt-6001"
}
```

### 6.2 ai.generation.failed

Published when a generation request fails after all retry and fallback attempts.

```json
{
  "event_id": "evt-b2c3d4e5f6a7",
  "event_type": "ai.generation.failed",
  "schema_version": "1.0",
  "timestamp": "2026-03-23T15:10:03Z",
  "user_id": "usr_9f2a7c41",
  "operation": "execute:tpl_chat_completion",
  "error_code": "PROVIDER_TIMEOUT",
  "retryable": true,
  "fallback_attempted": true,
  "correlation_id": "evt-001"
}
```

> **Note**: The `operation` field reflects the code path used:
> - Via `/execute`: `"execute:<template_id>"` (e.g., `"execute:tpl_chat_completion"`)
> - Via legacy `/chat-completions`: `"chat_completion"`
> - Via legacy `/summaries`: `"summary_generation"`
> - Via legacy `/proactive-messages`: `"proactive_message"`

---

## 7. Error Handling

| HTTP Status | Error Code | Description | Retryable |
|-------------|------------|-------------|-----------|
| 400 | `TEMPLATE_RENDER_ERROR` | Template not found or variable validation failed | No |
| 409 | (Conflict) | Duplicate template name+owner on registration | No |
| 422 | (Validation Error) | Request body validation failed | No |
| 500 | `PROVIDER_ERROR` | AI provider returned an error after all retries | No |
| 500 | `INTERNAL_ERROR` | Unexpected server error | No |
| 503 | `PROVIDER_TIMEOUT` | AI provider timed out after all retries | Yes |
| 503 | `CONVERSATION_STORE_UNAVAILABLE` | Failed to retrieve conversation messages from store | Yes |

**Error Response Body**:

```json
{
  "error_code": "TEMPLATE_RENDER_ERROR",
  "message": "Missing required variables for template 'tpl_proactive_outreach': user_prompt",
  "retryable": false,
  "correlation_id": "evt-6001"
}
```

---

## 8. Data Models

### PromptTemplate

| Field | Type | Description |
|-------|------|-------------|
| `template_id` | string | Unique template identifier (assigned on registration) |
| `name` | string | Human-readable name |
| `description` | string | Detailed description |
| `version` | string | Semantic version (auto-bumped on update) |
| `owner` | string | Owning service or team |
| `category` | string | Category for organization |
| `system_prompt` | string | System-level prompt managed by the AI service |
| `user_prompt_template` | string | User prompt with `{{variable}}` placeholders |
| `variables` | object | Variable schema (name -> TemplateVariableSchema) |
| `defaults` | TemplateDefaults | Default generation parameters |
| `tags` | array | Tags for filtering |
| `created_at` | datetime | Creation timestamp (ISO 8601) |
| `updated_at` | datetime | Last update timestamp (ISO 8601) |

### TemplateVariableSchema

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Variable data type: `string`, `number`, `boolean`, `object` |
| `required` | boolean | Whether the variable must be provided at generation time |
| `default` | any | Default value for optional variables |
| `description` | string | Human-readable description |

### TemplateDefaults

| Field | Type | Description |
|-------|------|-------------|
| `temperature` | float | Default sampling temperature (0.0-2.0) |
| `max_tokens` | int | Default max tokens (1-4096) |
| `top_p` | float | Default nucleus sampling (0.0-1.0) |
| `stop_sequences` | array | Default stop sequences |

### Preset Templates

The following templates are pre-loaded on service startup:

| Template ID | Version | Name | Category | Variables | Default Temp | Default Max Tokens |
|-------------|---------|------|----------|-----------|-------------|-------------------|
| `tpl_chat_completion` | 1.0.0 | Chat Completion | chat | `user_prompt` | 0.7 | 512 |
| `tpl_memory_compaction` | 2.0.0 | Memory Compaction Summary | summarization | `user_prompt` | 0.3 | 300 |
| `tpl_proactive_outreach` | 2.0.0 | Proactive Outreach Message | proactive | `user_prompt` | 0.8 | 150 |
| `tpl_sentiment_analysis` | 1.0.0 | Sentiment Analysis | analysis | `text`, `output_format` (opt) | 0.2 | 200 |
| `tpl_topic_extraction` | 1.0.0 | Topic Extraction | analysis | `conversation_text` | 0.2 | 300 |
| `tpl_safety_filter` | 1.0.0 | Safety Content Filter | safety | `content` | 0.0 | 200 |

> **Note**: The three core business templates (`tpl_chat_completion`, `tpl_memory_compaction`, `tpl_proactive_outreach`) all accept a single `user_prompt` variable. The caller is responsible for assembling the full prompt content; the AI service provides the system-level prompt (identity, safety, role instructions) via the template. See the [README](./README.md#calling-convention-for-business-services) for detailed usage examples per use case.
