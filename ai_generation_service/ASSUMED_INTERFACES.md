# AI Generation Service — Assumed External Interfaces

**Version**: 2.1
**Last Updated**: 2026-03-24
**Status**: Per-section statuses below. Last reviewed: 2026-03-24.

---

## Purpose

This document lists all external service interfaces that the AI Generation Service depends on but that are not yet formally defined or deployed. Each entry describes the assumed contract so that integration can proceed. Once the owning service publishes its official API, the corresponding assumption should be verified and this document updated accordingly.

---

## 1. Conversation Persistence Store — Message Window Retrieval

**Owner**: Platform / Data Team
**Status**: ⚠️ **Assumed Interface** — HTTP client is fully implemented in `services/conversation_store_client.py`, but the target endpoint has not been confirmed by the owning team. Currently no code path triggers this in production (the `/summaries` legacy endpoint that uses it has no active callers).

The AI Generation Service calls this endpoint when processing summary generation requests (legacy `POST /api/v1/generation/summaries` or via `execute` with `tpl_memory_compaction`). The summary request specifies a message window by ID range, and the service needs to retrieve the actual message content to build the summarization prompt.

**Assumed Endpoint**:

```
GET /api/v1/conversations/{conversation_id}/messages?from_id={from_message_id}&to_id={to_message_id}
```

**Assumed Base URL**: Configured via `AI_GEN_CONVERSATION_STORE_BASE_URL` environment variable.

**Assumed Request**:

| Parameter | Location | Type | Required | Description |
|-----------|----------|------|----------|-------------|
| `conversation_id` | path | string | yes | Conversation identifier |
| `from_id` | query | string | yes | Starting message ID (inclusive) |
| `to_id` | query | string | yes | Ending message ID (inclusive) |

**Assumed Response** `200 OK`:

```json
{
  "messages": [
    {
      "message_id": "msg-601",
      "role": "user",
      "content": "I went for a run this evening.",
      "timestamp": "2026-03-11T14:50:00Z"
    },
    {
      "message_id": "msg-602",
      "role": "assistant",
      "content": "That's great! How did it go?",
      "timestamp": "2026-03-11T14:50:03Z"
    }
  ]
}
```

**Notes**:

- Messages should be returned in chronological order.
- The response must include at least `role` and `content` fields per message.
- If the window contains no messages, an empty `messages` array should be returned.
- The architecture spec defines `POST /api/v1/conversations/{conversation_id}/messages` for writing messages. This read endpoint is assumed but not explicitly defined in the spec.

---

## 2. Internal Asynchronous Messaging Layer — Event Publishing

**Owner**: Platform / Infrastructure Team
**Status**: 🔶 **Stub** — Event schemas and publisher wrapper are implemented (`events/publisher.py`). The `_publish()` method logs events but does not send to a real broker. Broker technology decision is pending.

The AI Generation Service publishes events to two topics for telemetry and failure monitoring. The concrete broker technology (Redis Streams, RabbitMQ, SQS, or local in-process queue) has not been finalized.

**Assumed Topics**:

| Topic | Event Type | Description |
|-------|------------|-------------|
| `ai.generation.failed` | Failure notification | Published on hard generation failure |
| `ai.generation.completed` | Telemetry / audit trail | Published on successful generation |

**Assumed Publish Interface**:

The event publisher currently uses a stub implementation. The actual publish call is expected to follow one of these patterns depending on the chosen broker:

```python
# Redis Streams
await redis.xadd(topic, {"payload": json_payload})

# RabbitMQ
await channel.basic_publish(exchange="", routing_key=topic, body=json_payload)

# Local in-process queue
await queue.put({"topic": topic, "payload": json_payload})
```

**Configuration**: Broker URL is configured via `AI_GEN_EVENT_BROKER_URL` environment variable.

**Notes**:

- Event publishing failures must not break the main request flow. They are logged and swallowed.
- Events are JSON-serialized using the schemas defined in [API_INTERFACES.md](./API_INTERFACES.md#6-published-events).

---

## 3. Amazon Bedrock — Converse API

**Owner**: AWS / External
**Status**: ✅ **Implemented** — `services/bedrock_provider.py` fully implements the Converse API (text generation) and InvokeModel API (embeddings) with lazy client initialization, async executor wrapping, timeout handling, and error mapping. Requires `boto3` and valid AWS credentials (IAM role or env vars) at deploy time.

The primary AI provider uses the Amazon Bedrock Converse API to invoke Claude models for text generation, and the InvokeModel API for embeddings via Amazon Titan.

**Assumed SDK Call**:

```python
response = bedrock_client.converse(
    modelId="anthropic.claude-sonnet-4-20250514",
    messages=[
        {"role": "user", "content": [{"text": "Hello"}]}
    ],
    system=[{"text": "System prompt here"}],
    inferenceConfig={
        "temperature": 0.7,
        "maxTokens": 512
    }
)
```

**Assumed Response Structure**:

```json
{
  "output": {
    "message": {
      "role": "assistant",
      "content": [{"text": "Generated response"}]
    }
  },
  "usage": {
    "inputTokens": 100,
    "outputTokens": 50
  }
}
```

**Configuration**:

| Environment Variable | Description |
|---------------------|-------------|
| `AI_GEN_BEDROCK_REGION` | AWS region (default: ap-southeast-1) |
| `AI_GEN_BEDROCK_MODEL_ID` | Bedrock model identifier |
| `AI_GEN_BEDROCK_TIMEOUT_SECONDS` | Request timeout (default: 30s) |

**Assumed Embedding SDK Call (InvokeModel)**:

```python
response = bedrock_client.invoke_model(
    modelId="amazon.titan-embed-text-v2:0",
    contentType="application/json",
    accept="application/json",
    body='{"inputText": "Hello"}'
)
```

**Assumed Embedding Response Structure**:

```json
{
  "embedding": [0.0123, -0.0456, ...],
  "inputTextTokenCount": 5
}
```

**Notes**:

- AWS credentials are expected to be provided via IAM role (EC2 instance profile) or environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
- The Bedrock provider wraps the synchronous boto3 call in `asyncio.run_in_executor` for non-blocking operation.
- The embedding model is configured separately via `AI_GEN_BEDROCK_EMBEDDING_MODEL_ID` (default: `amazon.titan-embed-text-v2:0`).

---

## 4. Template Persistence (Future Enhancement)

**Owner**: AI Generation Service Team
**Status**: ✅ **Implemented (Local Only)** — Templates persist to local JSON files and in-memory store via `services/template_manager.py`. Functional for single-instance deployment. Multi-instance / production deployment requires a shared durable backend (not yet implemented).

Currently, prompt templates are stored in-memory and persisted as JSON files on the local filesystem. For production deployment, a durable storage backend is recommended.

**Assumed Future Options**:

| Option | Description |
|--------|-------------|
| DynamoDB / MySQL | Persistent storage with versioning |
| S3 | Template file storage with versioning |
| Redis | Fast template cache with TTL |

**Current Behavior**:

- Preset templates are loaded from `prompt_templates/` directory on startup.
- Dynamically registered templates are saved as JSON files in the same directory.
- A `template_index.json` file maintains the mapping of all registered templates.
- Template updates bump the patch version automatically.

**Notes**:

- The `TemplateManager` class is designed with a clean interface that can be backed by any storage implementation.
- Template registration and update operations are idempotent within the same service instance.
- Cross-instance consistency requires a shared storage backend (not yet implemented).

---

## Revision History

| Date | Change |
|------|--------|
| 2026-03-23 | v1.0 — Initial assumed interfaces documented |
| 2026-03-23 | v2.0 — Added template persistence future enhancement; updated for template-based architecture |
| 2026-03-24 | v2.1 — Replaced blanket "TO BE UPDATED" with per-section implementation statuses; Bedrock marked as fully implemented; added caller activity notes |
