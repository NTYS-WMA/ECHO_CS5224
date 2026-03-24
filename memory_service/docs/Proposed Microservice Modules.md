---
title: Proposed Microservice Modules

---

## 1. Channel Gateway Service

Receives inbound platform events, validates them, normalizes them into an internal message format, publishes inbound conversation events, consumes reply events, and sends the final reply back to the channel.

### Responsibilities

- Telegram webhook ingestion
- Command parsing such as `/start`, `/help`, and `/status`
- Channel-specific formatting
- Outbound delivery to Telegram

### Interfaces

#### 1. External inbound webhook from Telegram

**Source:** Telegram

**Destination:** Channel Gateway Service

**Type:** HTTP webhook

**Method:** `POST`

**Endpoint:** `/api/v1/channels/telegram/webhook`

```http
POST /api/v1/channels/telegram/webhook
```

**Payload**

```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 51,
    "date": 1773241800,
    "text": "Hello ECHO",
    "media": {},
    "from": {
      "id": 123456789,
      "is_bot": false,
      "first_name": "Alice",
      "username": "alice123",
      "language_code": "en"
    },
    "chat": {
      "id": 123456789,
      "first_name": "Alice",
      "username": "alice123",
      "type": "private"
    }
  }
}
```

**Expected response**

- HTTP 200 OK returned immediately after validation and successful event publication

#### 2. Internal event published to broker

**Source:** Channel Gateway Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `conversation.message.received`

**Payload**

```json
{
  "event_id": "evt-001",
  "event_type": "conversation.message.received",
  "timestamp": "2026-03-11T15:10:00Z",
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "channel": "telegram",
  "conversation_id": "telegram-chat-123456789",
  "channel_message_id": "tg-51",
  "message": {
    "role": "user",
    "type": "text",
    "content": "Hello ECHO"
  },
  "context": {
    "command": false,
    "received_at": "2026-03-11T15:10:00Z",
    "platform_user_id": "123456789",
    "platform_chat_id": "123456789",
    "username": "alice123"
  }
}
```

#### 3. Internal event consumed by orchestrator

**Source:** Internal Asynchronous Messaging Layer

**Destination:** Conversation Orchestrator Service

**Type:** Event consume

**Topic:** `conversation.message.received`

Consumes the normalized inbound message event published by Channel Gateway.

#### 4. Internal reply event published by orchestrator

**Source:** Conversation Orchestrator Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `conversation.outbound`

**Payload**

```json
{
  "event_id": "evt-002",
  "correlation_id": "evt-001",
  "event_type": "conversation.reply.generated",
  "timestamp": "2026-03-11T15:10:03Z",
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "channel": "telegram",
  "conversation_id": "telegram-chat-123456789",
  "responses": [
    {
      "type": "text",
      "content": "Hey Alice, nice to hear from you."
    }
  ]
}
```

#### 5. Internal reply event consumed by gateway

**Source:** Internal Asynchronous Messaging Layer

**Destination:** Channel Gateway Service / Channel Delivery Worker

**Type:** Event consume

**Topic:** `conversation.outbound`

Consumes the channel-agnostic reply event published by the Conversation Orchestrator.

#### 6. External outbound API call to Telegram

**Source:** Channel Gateway Service

**Destination:** Telegram Bot API

**Type:** External API call

**Method:** `POST`

**Operation:** `Telegram Bot API - sendMessage`

**Payload**

```json
{
  "chat_id": 123456789,
  "text": "Hey Alice, nice to hear from you."
}
```

The interaction between Channel Gateway and Conversation Orchestrator is modeled asynchronously so that the Telegram webhook can be acknowledged quickly, while AI processing, memory retrieval, and reply generation happen in the background without blocking the external channel callback.

## 1.5. Shared Platform Component: Internal Asynchronous Messaging Layer

The Internal Asynchronous Messaging Layer is the asynchronous messaging layer used for communication between internal services. It allows services to exchange events through topics or queues without requiring synchronous request-response coupling.

In the proposed design, the Internal Asynchronous Messaging Layer handles at least the following event channels:

- `conversation.message.received`
- `conversation.outbound`

And additional domain topics such as:

- `user.profile.updated`
- `relationship.interaction.recorded`
- `memory.summary.requested`
- `proactive.scan.requested`
- `media.asset.ready`

This component supports:

- Fast acknowledgment of external webhooks
- Decoupling between producers and consumers
- Buffering during traffic spikes
- Retry handling and resilience
- Easier scaling of downstream processing services

The Internal Asynchronous Messaging Layer is treated as an infrastructure component rather than a business microservice.

## 1.6. Shared Platform Component: Conversation Persistence Store

The Conversation Persistence Store is the canonical data component for raw conversation message persistence. It stores user and assistant turns with ordering, timestamps, and correlation metadata used for auditability and replay.

In the proposed design, Conversation Orchestrator writes canonical messages to this store through:

- `POST /api/v1/conversations/{conversation_id}/messages`

This component supports:

- Durable conversation history retention
- Ordered message replay for debugging and audit
- Source-of-truth chat transcript storage independent of vector memory
- Efficient retrieval for short-term memory adapters and analytics pipelines

The Conversation Persistence Store is treated as a shared platform/data component rather than a business microservice.

## 2. User Profile Service

Maintains canonical user identity and profile state, manages onboarding progression, stores user preferences and consent metadata, and emits profile-domain events for downstream personalization and proactive engagement.

Profiles are created implicitly on first interaction via upsert behavior on profile update operations. Path parameters use an internal URL-safe user ID (for example, `usr_9f2a7c41`) rather than channel-prefixed external identifiers.

### Responsibilities

- Create and maintain canonical user records
- Manage onboarding state transitions and completion status
- Store and update user preferences such as timezone, language, and interests
- Track consent and privacy flags for compliant feature usage
- Publish profile lifecycle updates for downstream consumers

### Interfaces

#### 1. Internal profile lookup request from orchestrator

**Source:** Conversation Orchestrator Service

**Destination:** User Profile Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/api/v1/users/{user_id}/profile`

```http
GET /api/v1/users/usr_9f2a7c41/profile
```

**Expected response**

```json
{
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "channel": "telegram",
  "display_name": "Alice",
  "username": "alice123",
  "language": "en",
  "timezone": "Asia/Singapore",
  "onboarding": {
    "state": "completed",
    "completed_at": "2026-03-10T09:00:00Z"
  },
  "preferences": {
    "tone": "friendly",
    "interests": ["fitness", "music"]
  },
  "consent": {
    "personalization": true,
    "proactive_messaging": true,
    "analytics": true
  },
  "account_tier": "free",
  "created_at": "2026-03-09T14:00:00Z",
  "updated_at": "2026-03-11T15:10:01Z"
}
```

#### 2. Internal partial profile update command

**Source:** Conversation Orchestrator Service

**Destination:** User Profile Service

**Type:** Internal API call

**Method:** `PATCH`

**Endpoint:** `/api/v1/users/{user_id}/profile`

```http
PATCH /api/v1/users/usr_9f2a7c41/profile
```

**Payload**

```json
{
  "channel": "telegram",
  "display_name": "Alice",
  "username": "alice123",
  "language": "en",
  "timezone": "Asia/Singapore",
  "preferences": {
    "interests": ["fitness", "music"]
  },
  "consent": {
    "personalization": true,
    "proactive_messaging": true,
    "analytics": true
  }
}
```

**Expected response**

- HTTP 200 OK with updated profile document

#### 3. Internal onboarding transition command

**Source:** Conversation Orchestrator Service

**Destination:** User Profile Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/users/{user_id}/onboarding/transitions`

```http
POST /api/v1/users/usr_9f2a7c41/onboarding/transitions
```

**Payload**

```json
{
  "event": "collect_timezone_completed",
  "from_state": "collect_timezone",
  "to_state": "collect_interests",
  "occurred_at": "2026-03-11T15:10:02Z",
  "metadata": {
    "source": "conversation_orchestrator",
    "correlation_id": "evt-001"
  }
}
```

**Expected response**

```json
{
  "user_id": "usr_9f2a7c41",
  "onboarding": {
    "state": "collect_interests",
    "previous_state": "collect_timezone",
    "updated_at": "2026-03-11T15:10:02Z"
  }
}
```

#### 4. Internal event published to broker on profile change

**Source:** User Profile Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `user.profile.updated`

**Payload**

```json
{
  "event_id": "evt-1001",
  "correlation_id": "evt-001",
  "event_type": "user.profile.updated",
  "timestamp": "2026-03-11T15:10:02Z",
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "channel": "telegram",
  "changes": {
    "timezone": "Asia/Singapore",
    "onboarding_state": "collect_interests"
  },
  "metadata": {
    "updated_by": "conversation_orchestrator",
    "source": "onboarding_transition"
  },
  "profile_version": 7,
  "schema_version": "1.0"
}
```

#### 5. Internal event consumed by downstream services

**Source:** Internal Asynchronous Messaging Layer

**Destination:** Eligible downstream consumers

**Type:** Event consume

**Topic:** `user.profile.updated`

Eligible downstream consumers (for example, Relationship Service, Proactive Engagement Service, and Conversation Orchestrator Service) consume profile updates to refresh personalization context, relationship modeling inputs, and proactive engagement eligibility.

## 3. Conversation Orchestrator Service

Saves the message, publishes relationship interaction updates, gets short-term context, gets long-term memories, builds the system prompt, calls Claude, saves the reply, and may summarize.

### Responsibilities

- Consume inbound conversation events and coordinate end-to-end reply generation
- Retrieve user profile, consent, onboarding, and personalization context
- Retrieve short-term and long-term memory context for prompt grounding
- Publish relationship interaction events based on each interaction
- Invoke AI generation and apply fallback/error handling policy
- Persist inbound and outbound conversation messages for audit and context continuity
- Trigger summarization for long conversations via asynchronous memory workflows
- Publish outbound reply events and workflow-status events

### Interfaces

#### 1. Internal inbound event consumed from broker

**Source:** Internal Asynchronous Messaging Layer

**Destination:** Conversation Orchestrator Service

**Type:** Event consume

**Topic:** `conversation.message.received`

Consumes normalized user message events from Channel Gateway and starts orchestration workflow.

#### 2. Internal profile context lookup

**Source:** Conversation Orchestrator Service

**Destination:** User Profile Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/api/v1/users/{user_id}/profile`

```http
GET /api/v1/users/usr_9f2a7c41/profile
```

**Expected response**

```json
{
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "channel": "telegram",
  "language": "en",
  "timezone": "Asia/Singapore",
  "account_tier": "free",
  "onboarding": {
    "state": "completed"
  },
  "preferences": {
    "tone": "friendly",
    "interests": ["fitness", "music"],
    "quiet_hours": {
      "start": "22:00",
      "end": "07:00"
    }
  },
  "consent": {
    "personalization": true,
    "proactive_messaging": true
  }
}
```

#### 3. Internal memory context retrieval request

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/memory/context`

```http
POST /api/v1/memory/context
```

**Payload**

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "query": "Hello ECHO",
  "limits": {
    "short_term_messages": 12,
    "long_term_memories": 5
  },
  "correlation_id": "evt-001"
}
```

**Expected response**

```json
{
  "short_term": [
    {
      "role": "assistant",
      "content": "How was your run today?"
    }
  ],
  "long_term": [
    {
      "memory_id": "mem-901",
      "content": "User prefers evening workouts",
      "score": 0.88
    }
  ]
}
```

#### 4. Internal conversation message persistence request

**Source:** Conversation Orchestrator Service

**Destination:** Conversation Persistence Store

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/conversations/{conversation_id}/messages`

```http
POST /api/v1/conversations/telegram-chat-123456789/messages
```

**Payload**

```json
{
  "user_id": "usr_9f2a7c41",
  "channel": "telegram",
  "messages": [
    {
      "role": "user",
      "type": "text",
      "content": "Hello ECHO",
      "timestamp": "2026-03-11T15:10:00Z"
    },
    {
      "role": "assistant",
      "type": "text",
      "content": "Hey Alice, nice to hear from you.",
      "timestamp": "2026-03-11T15:10:03Z"
    }
  ],
  "correlation_id": "evt-001"
}
```

**Expected response**

- HTTP 201 Created

#### 5. Internal relationship update event published to broker

**Source:** Conversation Orchestrator Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `relationship.interaction.recorded`

**Payload**

```json
{
  "event_id": "evt-021",
  "correlation_id": "evt-001",
  "event_type": "relationship.interaction.recorded",
  "timestamp": "2026-03-11T15:10:03Z",
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "conversation_id": "telegram-chat-123456789",
  "sentiment": "positive",
  "message_count_delta": 1
}
```

#### 6. Internal AI generation request

**Source:** Conversation Orchestrator Service

**Destination:** AI Generation Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/generation/chat-completions`

```http
POST /api/v1/generation/chat-completions
```

**Payload**

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
    "max_tokens": 200
  },
  "correlation_id": "evt-001"
}
```

**Expected response**

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

#### 7. Internal summarization request event published to broker

**Source:** Conversation Orchestrator Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `memory.summary.requested`

**Payload**

```json
{
  "event_id": "evt-022",
  "correlation_id": "evt-001",
  "event_type": "memory.summary.requested",
  "timestamp": "2026-03-11T15:10:04Z",
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "window": {
    "from_message_id": "msg-601",
    "to_message_id": "msg-645"
  },
  "trigger": "conversation_length_threshold"
}
```

#### 8. Internal reply event published to broker

**Source:** Conversation Orchestrator Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `conversation.outbound`

**Payload**

```json
{
  "event_id": "evt-002",
  "correlation_id": "evt-001",
  "event_type": "conversation.reply.generated",
  "timestamp": "2026-03-11T15:10:03Z",
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "channel": "telegram",
  "conversation_id": "telegram-chat-123456789",
  "responses": [
    {
      "type": "text",
      "content": "Hey Alice, nice to hear from you."
    }
  ],
  "metadata": {
    "profile_version": 7,
    "memory_context_used": true
  }
}
```

#### 9. Internal workflow failure event published to broker

**Source:** Conversation Orchestrator Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `conversation.processing.failed`

**Payload**

```json
{
  "event_id": "evt-003",
  "correlation_id": "evt-001",
  "event_type": "conversation.processing.failed",
  "timestamp": "2026-03-11T15:10:03Z",
  "user_id": "usr_9f2a7c41",
  "external_user_id": "telegram:123456789",
  "conversation_id": "telegram-chat-123456789",
  "stage": "ai_generation",
  "error_code": "AI_TIMEOUT",
  "retryable": true
}
```

## 4. Memory Service

Stores, retrieves, and searches long-term vector memories derived from conversation messages, and maintains evidence-backed user profiles extracted from conversation content.

The service runs on port `18088` and exposes a REST API. It uses PostgreSQL with pgvector for vector memory storage, MongoDB for extended user profile attributes, and SQLite for memory change history. All embedding and LLM operations are performed internally; callers only supply raw messages.

### Responsibilities

- Extract and persist semantic memories from conversation messages via LLM-driven summarization
- Serve semantically relevant memories for a given query via vector similarity search
- Maintain a full audit trail of memory changes
- Extract and update structured user profiles (basic info + interests, skills, personality) from conversation messages
- Support cold-start profile seeding from an external MainService on first access

### Interfaces

#### 1. Add memories from messages

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/memories`

```http
POST /memories
```

**Payload**

```json
{
  "messages": [
    {"role": "user", "content": "I usually go running after dinner."},
    {"role": "assistant", "content": "That sounds like a great evening routine!"}
  ],
  "user_id": "usr_9f2a7c41"
}
```

At least one of `user_id`, `agent_id`, or `run_id` is required. An optional `metadata` field accepts a free-form object.

**Expected response**

```json
{
  "results": [
    {
      "id": "mem-901",
      "memory": "User prefers evening runs after dinner.",
      "event": "ADD"
    }
  ]
}
```

#### 2. Retrieve all memories for a user

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/memories`

```http
GET /memories?user_id=usr_9f2a7c41
```

Query parameters: `user_id`, `agent_id`, `run_id` (at least one required).

**Expected response**

```json
{
  "results": [
    {
      "id": "mem-901",
      "memory": "User prefers evening runs after dinner.",
      "user_id": "usr_9f2a7c41",
      "created_at": "2026-03-11T15:10:04Z",
      "updated_at": "2026-03-11T15:10:04Z"
    }
  ]
}
```

#### 3. Search memories by semantic query

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/search`

```http
POST /search
```

**Payload**

```json
{
  "query": "what does the user like to do in the evening?",
  "user_id": "usr_9f2a7c41",
  "limit": 5,
  "threshold": 0.7
}
```

`limit` defaults to 5. `threshold` is optional (0.0–1.0 similarity floor). `filters` accepts an optional metadata filter object.

**Expected response**

```json
{
  "results": [
    {
      "id": "mem-901",
      "memory": "User prefers evening runs after dinner.",
      "score": 0.91,
      "user_id": "usr_9f2a7c41"
    }
  ]
}
```

#### 4. Retrieve a specific memory

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/memories/{memory_id}`

```http
GET /memories/mem-901
```

**Expected response**

```json
{
  "id": "mem-901",
  "memory": "User prefers evening runs after dinner.",
  "user_id": "usr_9f2a7c41",
  "created_at": "2026-03-11T15:10:04Z",
  "updated_at": "2026-03-11T15:10:04Z"
}
```

#### 5. Update a memory

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `PUT`

**Endpoint:** `/memories/{memory_id}`

```http
PUT /memories/mem-901
```

**Payload**

```json
{
  "data": "User prefers evening runs, typically after 7 PM."
}
```

**Expected response**

```json
{
  "id": "mem-901",
  "memory": "User prefers evening runs, typically after 7 PM."
}
```

#### 6. Delete a specific memory

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `DELETE`

**Endpoint:** `/memories/{memory_id}`

```http
DELETE /memories/mem-901
```

**Expected response**

```json
{"message": "Memory deleted successfully"}
```

#### 7. Delete all memories for a user

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `DELETE`

**Endpoint:** `/memories`

```http
DELETE /memories?user_id=usr_9f2a7c41
```

Query parameters: `user_id`, `agent_id`, `run_id` (at least one required).

**Expected response**

```json
{"message": "All relevant memories deleted"}
```

#### 8. Get memory change history

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/memories/{memory_id}/history`

```http
GET /memories/mem-901/history
```

**Expected response**

```json
[
  {
    "id": "hist-001",
    "memory_id": "mem-901",
    "prev_value": null,
    "new_value": "User prefers evening runs after dinner.",
    "event": "ADD",
    "timestamp": "2026-03-11T15:10:04Z"
  }
]
```

#### 9. Extract and update user profile from messages

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/profile`

```http
POST /profile
```

The service runs a two-stage LLM pipeline: it first extracts structured profile information from the messages, then decides which fields to add, update, or delete relative to the existing profile. Basic info is stored in PostgreSQL; extended attributes (interests, skills, personality, social context) are stored in MongoDB.

**Payload**

```json
{
  "user_id": "usr_9f2a7c41",
  "messages": [
    {"role": "user", "content": "I'm a software engineer at Google, living in Singapore."},
    {"role": "assistant", "content": "That's great! What do you enjoy working on?"},
    {"role": "user", "content": "Mostly backend systems. I also love hiking on weekends."}
  ]
}
```

**Expected response**

```json
{
  "success": true,
  "basic_info_updated": true,
  "additional_profile_updated": true,
  "operations_performed": {
    "added": 2,
    "updated": 1,
    "deleted": 0
  },
  "errors": []
}
```

#### 10. Retrieve user profile

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/profile`

```http
GET /profile?user_id=usr_9f2a7c41&fields=interests,skills&evidence_limit=3
```

Query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | — | Required |
| `fields` | string | all | Comma-separated list of `additional_profile` fields to return (e.g. `interests,skills,personality`) |
| `evidence_limit` | int | 5 | Number of evidence items to return per attribute. `0` = none, `-1` = all |

If the user has no profile and MainService cold-start is configured, the service attempts to seed an initial profile from MainService before returning.

**Expected response**

```json
{
  "user_id": "usr_9f2a7c41",
  "basic_info": {
    "name": "Alice",
    "current_city": "Singapore",
    "occupation": "software engineer",
    "company": "Google",
    "education_level": "master",
    "university": "NUS",
    "major": "Computer Science"
  },
  "additional_profile": {
    "interests": [
      {
        "id": "int-001",
        "name": "hiking",
        "degree": 4,
        "evidence": [
          {"text": "I love hiking on weekends.", "timestamp": "2026-03-11T15:10:04Z"}
        ]
      }
    ],
    "skills": [
      {
        "id": "skl-001",
        "name": "backend systems",
        "degree": 4,
        "evidence": [
          {"text": "Mostly backend systems.", "timestamp": "2026-03-11T15:10:04Z"}
        ]
      }
    ]
  }
}
```

`basic_info` field list: `name`, `nickname`, `english_name`, `birthday`, `gender`, `nationality`, `hometown`, `current_city`, `timezone`, `language`, `occupation`, `company`, `education_level`, `university`, `major`.

#### 11. Get missing profile fields

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/profile/missing-fields`

```http
GET /profile/missing-fields?user_id=usr_9f2a7c41&source=both
```

Query parameters: `user_id` (required), `source` (`pg` / `mongo` / `both`, default `both`).

**Expected response**

```json
{
  "user_id": "usr_9f2a7c41",
  "missing_fields": {
    "basic_info": ["birthday", "hometown", "gender"],
    "additional_profile": ["personality", "learning_preferences"]
  }
}
```

#### 12. Delete user profile

**Source:** Conversation Orchestrator Service

**Destination:** Memory Service

**Type:** Internal API call

**Method:** `DELETE`

**Endpoint:** `/profile`

```http
DELETE /profile?user_id=usr_9f2a7c41
```

**Expected response**

```json
{
  "success": true,
  "basic_info_deleted": true,
  "additional_profile_deleted": true
}
```

### Sub-capabilities

- Long-term vector memory (pgvector + HNSW index)
- Memory change history (SQLite audit log)
- User profile extractor (LLM two-stage pipeline)
- Evidence-backed profile store (PostgreSQL + MongoDB)

## 5. Relationship Service

Models the friendship level or relationship score and updates it based on sentiment plus inactivity decay.

Relationship state is user-level and cross-channel by default, with optional per-channel interaction counters retained for analytics and diagnostics.

### Responsibilities

- Compute and maintain per-user relationship affinity scores and tiers on a 0-1 scale.
- Score completed conversation sessions via AI — not per individual message. A session ends when the user has been silent for 30 minutes. Scoring considers overall sentiment, engagement depth, trust signals, unanswered proactive messages from ECHO, and inactivity duration.
- Apply inactivity decay on schedule-driven intervals
- Serve relationship context for orchestration and personalization decisions
- Publish relationship state changes for eligible downstream consumers

Affinity scores map to four tiers:

Score	Tier
0.00 – 0.30	acquaintance
0.31 – 0.60	friend
0.61 – 0.80	close_friend
0.81 – 1.00	best_friend


### Interfaces

#### 1. Internal interaction event consumed from Cron Scheduler

**Source:** Cron Service

**Destination:** Relationship Service

**Type:** Direct function call

**Topic:** `relationship.interaction.recorded`

**Payload**

```json
{
 "event_id": "evt-021",
 "correlation_id": "evt-001",
 "event_type": "relationship.interaction.recorded",
 "schema_version": "1.0",
 "timestamp": "2026-03-11T15:10:03Z",
 "user_id": "usr_9f2a7c41",
 "external_user_id": "telegram:123456789",
 "channel": "telegram",
 "conversation_id": "telegram-chat-123456789",
 "last_message_at": "2026-03-11T15:10:03Z"
 }
```

Consumes interaction events emitted by Conversation Orchestrator to update affinity score, counters, and recency metrics.

#### 2. Internal profile update event consumed from broker

**Source:** Internal Asynchronous Messaging Layer

**Destination:** Relationship Service

**Type:** Event consume

**Topic:** `user.profile.updated`

Consumes profile updates to adjust relationship modeling context such as onboarding state, consent eligibility, and personalization settings.

#### 3. Internal relationship context lookup

**Source:** Conversation Orchestrator Service

**Destination:** Relationship Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/api/v1/relationships/{user_id}/context`

```http
GET /api/v1/relationships/usr_9f2a7c41/context
```

**Expected response**

```json
{
  "user_id": "usr_9f2a7c41",
  "affinity_score": 0.74,
  "tier": "close_friend",
  "interaction_count": 128,
  "last_interaction_at": "2026-03-11T15:10:03Z",
  "decay_state": {
    "last_decay_at": "2026-03-12T00:00:00Z",
    "days_inactive": 0
  },
  "updated_at": "2026-03-12T00:00:00Z"
}
```

#### 4. Internal relationship state change event published to broker

**Source:** Relationship Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `relationship.score.updated`

**Payload**

```json
{
  "event_id": "evt-4001",
  "correlation_id": "evt-021",
  "event_type": "relationship.score.updated",
  "schema_version": "1.0",
  "timestamp": "2026-03-11T15:10:04Z",
  "user_id": "usr_9f2a7c41",
  "previous_score": 0.72,
  "new_score": 0.74,
  "previous_tier": "friend",
  "new_tier": "close_friend",
  "reason": "positive_interaction"
}
```

#### 5. Internal inactivity decay trigger event consumed from broker

**Source:** Internal Asynchronous Messaging Layer

**Destination:** Relationship Service

**Type:** Event consume

**Topic:** `relationship.decay.requested`

**Payload**

```json
{
  "event_id": "evt-5001",
  "event_type": "relationship.decay.requested",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T00:00:00Z",
  "mode": "batch",
  "batch": {
    "segment": "all_active_users",
    "limit": 10000
  },
  "requested_by": "proactive_engagement_scheduler"
}
```

Consumes scheduler-driven decay triggers to apply inactivity penalties in batch or incremental mode.

## 6. AI Generation Service

Provides model-agnostic text generation capabilities for conversational replies, memory summarization, and proactive engagement prompts, with retry/fallback behavior and generation telemetry.

### Responsibilities

- Handle provider-agnostic chat completion requests
- Apply provider-specific request transformation and model request shaping
- Generate summarization outputs for memory compaction workflows
- Generate proactive outreach message drafts when requested
- Apply model fallback and timeout retry policies
- Return usage and generation metadata for observability and governance

For synchronous API calls, AI Generation Service returns an immediate error response to the caller on hard failures (for example provider timeout or validation error), and may additionally publish `ai.generation.failed` for asynchronous monitoring and incident workflows.

### Interfaces

#### 1. Internal chat completion request

**Source:** Conversation Orchestrator Service

**Destination:** AI Generation Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/generation/chat-completions`

```http
POST /api/v1/generation/chat-completions
```

**Payload**

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
    "max_tokens": 200
  },
  "correlation_id": "evt-001"
}
```

**Expected response**

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

#### 2. Internal summary generation request

**Source:** Memory Service

**Destination:** AI Generation Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/generation/summaries`

```http
POST /api/v1/generation/summaries
```

**Payload**

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

**Expected response**

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

#### 3. Internal proactive message generation request

**Source:** Proactive Engagement Service

**Destination:** AI Generation Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/generation/proactive-messages`

```http
POST /api/v1/generation/proactive-messages
```

**Payload**

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

**Expected response**

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

#### 4. Internal generation failure event published to broker

**Source:** AI Generation Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `ai.generation.failed`

**Payload**

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

#### 5. Internal generation telemetry event published to broker

**Source:** AI Generation Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `ai.generation.completed`

Published for telemetry, monitoring, and audit trails only; it is not a second business response path.

**Payload**

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

## 7. Proactive Engagement Service

Determines when ECHO should initiate outbound engagement, selects eligible users based on inactivity and policy checks, requests proactive message drafts, and publishes outbound conversation events.

### Responsibilities

- Evaluate proactive engagement eligibility windows and consent constraints
- Run scheduled inactivity scans and candidate selection workflows
- Enforce consent, quiet-hours, and eligibility policy checks before AI generation
- Request AI-generated proactive message drafts
- Publish proactive outbound messages to the main delivery pipeline
- Emit engagement telemetry for monitoring and campaign analysis

### Interfaces

#### 1. Internal scheduler trigger event consumed from broker

**Source:** Internal Asynchronous Messaging Layer

**Destination:** Proactive Engagement Service

**Type:** Event consume

**Topic:** `proactive.scan.requested`

**Payload**

```json
{
  "event_id": "evt-7001",
  "event_type": "proactive.scan.requested",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T09:00:00Z",
  "window": {
    "timezone": "Asia/Singapore",
    "hour": 9
  },
  "mode": "scheduled"
}
```

Consumes scheduler-driven scan triggers to start proactive candidate selection.

#### 2. Internal candidate selection request

**Source:** Proactive Engagement Service

**Destination:** Relationship Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/relationships/proactive-candidates/search`

```http
POST /api/v1/relationships/proactive-candidates/search
```

**Payload**

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

**Expected response**

```json
{
  "candidates": [
    {
      "user_id": "usr_9f2a7c41",
      "days_inactive": 3,
      "affinity_score": 0.74
    }
  ]
}
```

#### 3. Internal profile/consent lookup request

**Source:** Proactive Engagement Service

**Destination:** User Profile Service

**Type:** Internal API call

**Method:** `GET`

**Endpoint:** `/api/v1/users/{user_id}/profile`

```http
GET /api/v1/users/usr_9f2a7c41/profile
```

**Expected response**

```json
{
  "user_id": "usr_9f2a7c41",
  "consent": {
    "proactive_messaging": true
  },
  "preferences": {
    "quiet_hours": {
      "start": "22:00",
      "end": "07:00"
    }
  },
  "timezone": "Asia/Singapore"
}
```

Per-user profile lookup is acceptable for MVP. At scale, batch lookup or a precomputed eligibility index should be considered to avoid N+1 query overhead.

#### 4. Internal proactive generation request

**Source:** Proactive Engagement Service

**Destination:** AI Generation Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/generation/proactive-messages`

```http
POST /api/v1/generation/proactive-messages
```

This request is invoked only after consent checks, quiet-hours checks, and eligibility policy checks pass.

**Payload**

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
  "correlation_id": "evt-7001"
}
```

**Expected response**

```json
{
  "response_id": "gen-980",
  "output": [
    {
      "type": "text",
      "content": "Hey Alice, just checking in—how has your week been so far?"
    }
  ],
  "model": "claude-sonnet"
}
```

#### 5. Internal proactive outbound event published to broker

**Source:** Proactive Engagement Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `conversation.outbound`

**Payload**

````json
{
  "event_id": "evt-7002",
  "correlation_id": "evt-7001",
  "event_type": "conversation.reply.generated",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T09:00:02Z",
  "user_id": "usr_9f2a7c41",
  "channel": "telegram",
  "conversation_id": "telegram-chat-123456789",
  "responses": [
    {
      "type": "text",
      "content": "Hey Alice, just checking in—how has your week been so far?"
    }
  ],
#### 6. Internal proactive telemetry event published to broker

**Source:** Proactive Engagement Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `proactive.dispatch.completed`

**Payload**

```json
{
  "event_id": "evt-7003",
  "correlation_id": "evt-7001",
  "event_type": "proactive.dispatch.completed",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T09:00:03Z",
  "stats": {
    "candidates_scanned": 500,
    "messages_dispatched": 127,
    "messages_skipped": 373
  }
}
````

## 8. Media Service

Provides media generation and storage workflows for non-text responses, including text-to-speech rendering, object storage upload, and signed URL issuance for downstream channel delivery.

### Responsibilities

- Generate audio assets from text via text-to-speech engines
- Upload generated media to object storage
- Issue time-bound signed URLs for delivery consumption
- Publish media generation completion and failure events
- Support future media enrichment flows such as image generation

### Interfaces

#### 1. Internal media generation request

**Source:** Conversation Orchestrator Service

**Destination:** Media Service

**Type:** Internal API call

**Method:** `POST`

**Endpoint:** `/api/v1/media/generate`

```http
POST /api/v1/media/generate
```

**Payload**

```json
{
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "type": "tts",
  "input": {
    "text": "Hey Alice, nice to hear from you.",
    "voice_profile": "friendly_female_en_sg",
    "language": "en"
  },
  "correlation_id": "evt-8001"
}
```

**Expected response**

```json
{
  "media_job_id": "job-9001",
  "status": "accepted"
}
```

This operation is asynchronous. Callers should rely on `media.asset.ready` and `media.generation.failed` events for completion.

#### 2. Internal storage upload operation

**Source:** Media Service

**Destination:** Object Storage Platform

**Type:** Platform storage operation

**Operation:** `PutObject`

**Object key:** `media/tts/usr_9f2a7c41/job-9001.mp3`

**Expected response**

- HTTP 201 Created

#### 3. Internal signed URL generation operation

**Source:** Media Service

**Destination:** Object Storage Platform

**Type:** Platform storage operation

**Operation:** `GeneratePresignedUrl`

**Object key:** `media/tts/usr_9f2a7c41/job-9001.mp3`

**Payload**

```json
{
  "expires_in_seconds": 3600,
  "method": "GET"
}
```

**Expected response**

```json
{
  "url": "https://storage.example.com/signed/abc123",
  "expires_at": "2026-03-12T10:00:05Z"
}
```

Signed URLs are intended for internal delivery components and are passed into channel delivery operations only when the target channel supports URL-based media pull.

#### 4. Internal media completion event published to broker

**Source:** Media Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `media.asset.ready`

**Payload**

```json
{
  "event_id": "evt-8002",
  "correlation_id": "evt-8001",
  "event_type": "media.asset.ready",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T09:00:05Z",
  "user_id": "usr_9f2a7c41",
  "conversation_id": "telegram-chat-123456789",
  "media": {
    "type": "audio",
    "mime_type": "audio/mpeg",
    "object_key": "media/tts/usr_9f2a7c41/job-9001.mp3",
    "signed_url": "https://storage.example.com/signed/abc123"
  }
}
```

Consumed by Conversation Orchestrator Service and Channel Gateway delivery workers to continue outbound delivery with media attachments.

#### 5. Internal media failure event published to broker

**Source:** Media Service

**Destination:** Internal Asynchronous Messaging Layer

**Type:** Event publish

**Topic:** `media.generation.failed`

**Payload**

```json
{
  "event_id": "evt-8003",
  "correlation_id": "evt-8001",
  "event_type": "media.generation.failed",
  "schema_version": "1.0",
  "timestamp": "2026-03-12T09:00:04Z",
  "user_id": "usr_9f2a7c41",
  "operation": "tts",
  "error_code": "TTS_PROVIDER_UNAVAILABLE",
  "retryable": true
}
```

Consumed by Conversation Orchestrator Service for retry/fallback policy and by observability systems for alerting.

## Which parts of the app run on which AWS service/component

### External to AWS

- **Telegram User**  
  End user interacting with the bot.

- **Telegram Bot API**  
  External messaging platform API used for inbound webhooks and outbound message delivery.

---

### Ingress layer (single EC2)

These components run on the EC2 host and handle lightweight ingress and delivery logic.

- **Nginx ingress gateway**  
  Routes incoming requests to local services on the EC2 host.

- **Channel Gateway Service on EC2**  
  Runs the inbound adapter logic:
  - validate webhook payload
  - normalize Telegram message format into internal event format
  - publish inbound conversation event into the local async queue

- **Outbound delivery worker on EC2**  
  Runs the outbound adapter logic:
  - consume outbound delivery event
  - transform internal message payload into Telegram API request
  - send message/media back through Telegram Bot API

---

### Messaging backbone (single EC2)

These components are local to the EC2 host and decouple services and background work.

- **Local async queue / job broker**  
  Carries domain events across the local runtime, such as:
  - `conversation.message.received`
  - `conversation.outbound`
  - `media.asset.ready`
  - proactive engagement events

- **Local worker queues**  
  Holds asynchronous background jobs for services that do not require strict ordering, such as:
  - relationship updates
  - memory processing
  - proactive engagement tasks
  - media processing

- **Local scheduler / cron worker**  
  Triggers scheduled jobs, such as:
  - proactive engagement scans
  - periodic maintenance or housekeeping workflows
  - time-based reminders or follow-up events

---

### Core application services

These are the main business services deployed as co-located processes on a single EC2 instance. The services remain logically separated, but are deployed together on one EC2 host.

- **Conversation Orchestrator Service**  
  Main runtime brain of the app. It:
  - consumes ordered conversation events
  - fetches profile, relationship, and memory context
  - calls AI generation
  - decides the next response/action
  - emits outbound conversation events

- **User Profile Service**  
  Manages user profile data and preferences, such as:
  - user attributes
  - consent flags
  - quiet hours
  - user-level settings

- **Relationship Service**  
  Maintains social/relationship context, such as:
  - affinity score
  - relationship state
  - decay logic
  - interaction-based updates

- **Memory Service**  
  Handles conversational memory logic, such as:
  - retrieving recent turns
  - writing summaries
  - reading/writing long-term semantic memory
  - preparing memory context for generation

- **AI Generation Service**  
  Encapsulates model invocation logic. It:
  - builds prompts
  - calls foundation models
  - returns generated text or AI outputs to the orchestrator or proactive service

- **Proactive Engagement Service**  
  Runs outbound re-engagement logic, such as:
  - inactivity scans
  - consent and quiet-hour checks
  - candidate selection
  - proactive message draft requests
  - publishing proactive outbound events

- **Media Service**  
  Handles media-related workflows, such as:
  - optional TTS/media generation
  - preparing media assets
  - storing/retrieving media objects
  - returning `media.asset.ready` events

---

### Data storage components

These are backing stores used by the services above.

- **Aurora PostgreSQL Serverless v2 + pgvector**  
  Stores persistent conversations and long-term semantic memory, such as:
  - raw turns and conversation history
  - user profiles and relationship state
  - embeddings and memory records
  - vector similarity search results

- **S3 – Media Assets**  
  Stores:
  - generated media
  - uploaded objects
  - asset files
  - presigned URL-backed media delivery artifacts

---

### AI platform

- **Amazon Bedrock (Claude models)**  
  Provides the LLM runtime used by the **AI Generation Service** for:
  - reply generation
  - summarization
  - proactive message drafting
  - other AI text-generation tasks

---

### Observability

- **CloudWatch Logs / Metrics / Alarms**  
  Used across the platform for:
  - application logs
  - metrics
  - health monitoring
  - alerting
  - operational dashboards

---

## Simple summary

In this architecture:

- **One EC2 instance** runs the main ECHO application services
- **Nginx ingress gateway** routes incoming requests to local services on the EC2 host
- **Local async workers / scheduler / job queue** handle background processing on the EC2 host
- **Aurora PostgreSQL Serverless v2 + pgvector** stores persistent conversations and long-term semantic memory
- **S3** stores media assets
- **Bedrock** provides AI model inference
- **CloudWatch** provides monitoring and alerts
- **Route 53 + Application Load Balancer** provide the public entry point

![Screenshot 2026-03-16 130326](https://hackmd.io/_uploads/BymS1fB5Wg.jpg)