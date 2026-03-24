# AI Generation Service

The AI Generation Service is the **AI execution engine** for the ECHO platform. It provides model-agnostic text generation with centralized **prompt template management**. Business services register, query, and reference prompt templates by ID, while the AI service handles template rendering, provider invocation, retry/fallback, and telemetry.

---

## Architecture Position

```
                                  ┌──────────────────────────────────────┐
                                  │       AI Generation Service          │
                                  │                                      │
  Business Callers                │  ┌──────────────┐  ┌─────────────┐  │
  ─────────────────               │  │   Template    │  │  Template   │  │
  Channel Gateway Orchestrator ──▶│  │   Manager     │  │  Renderer   │  │
  (other business services) ─────▶│  │  (CRUD+Store) │  │ (Render)    │  │
                                  │  └──────┬───────┘  └──────┬──────┘  │
                                  │         │                  │         │
                                  │         ▼                  ▼         │
                                  │  ┌──────────────────────────────┐   │
                                  │  │     Generation Service       │   │
                                  │  │  (Retry + Fallback Engine)   │   │
                                  │  └──────────┬───────────────────┘   │
                                  └─────────────┼───────────────────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              ▼                                   ▼
                     Amazon Bedrock (Claude)            Fallback Provider
                       (Primary)                       (OpenAI-compatible)
```

**Design Principles**:

- **Business callers own prompt content**: Callers assemble the core prompt (variables, messages). The AI service does NOT embed business logic.
- **AI service owns system-level prompts**: System prompts, variable schemas, and default parameters are managed as templates.
- **Template-first invocation**: The primary `/execute` endpoint takes a `template_id` + `variables` (or `messages`).
- **Parameter priority chain**: Caller Config > Template Defaults > Service Defaults.

---

## Directory Structure

```
ai_generation_service/
├── __init__.py
├── app.py                              # FastAPI application entry point
├── requirements.txt                    # Python dependencies
├── API_INTERFACES.md                   # API interface reference for callers
├── ASSUMED_INTERFACES.md               # Assumed external interfaces (TO BE UPDATED)
├── README.md                           # This file
├── prompt_templates/                   # Prompt template JSON files
│   ├── chat_completion.json            # Preset: multi-turn chat
│   ├── memory_compaction.json          # Preset: memory summarization
│   ├── proactive_outreach.json         # Preset: proactive re-engagement
│   ├── sentiment_analysis.json         # Preset: sentiment analysis
│   ├── topic_extraction.json           # Preset: topic extraction
│   └── safety_filter.json             # Preset: content safety filter
├── config/
│   ├── __init__.py
│   └── settings.py                     # Configuration via environment variables
├── models/
│   ├── __init__.py
│   ├── requests.py                     # Request Pydantic models
│   ├── responses.py                    # Response Pydantic models
│   ├── events.py                       # Event Pydantic models
│   └── templates.py                    # Prompt template Pydantic models
├── routes/
│   ├── __init__.py
│   ├── generation_routes.py            # /api/v1/generation/* endpoints
│   ├── template_routes.py             # /api/v1/templates/* endpoints
│   └── health_routes.py               # /health and /ready endpoints
├── services/
│   ├── __init__.py
│   ├── provider_base.py               # Abstract AI provider interface
│   ├── bedrock_provider.py            # Amazon Bedrock (Claude) provider
│   ├── fallback_provider.py           # OpenAI-compatible fallback provider
│   ├── template_manager.py            # Template CRUD and storage
│   ├── template_renderer.py           # Template rendering engine
│   ├── conversation_store_client.py   # Client for Conversation Persistence Store
│   └── generation_service.py          # Core execution engine with retry/fallback
├── events/
│   ├── __init__.py
│   └── publisher.py                   # Event publisher for messaging layer
├── utils/
│   ├── __init__.py
│   └── helpers.py                     # ID generation and utility functions
└── tests/
    ├── __init__.py
    └── test_generation_routes.py      # Unit tests (37 tests)
```

---

## API Endpoints

### Template Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/templates` | Register a new prompt template |
| GET | `/api/v1/templates` | List all templates (with optional filters) |
| GET | `/api/v1/templates/{template_id}` | Get template by ID |
| PUT | `/api/v1/templates/{template_id}` | Update an existing template |

### Generation

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| POST | `/api/v1/generation/execute` | **Primary** — template_id + variables/messages | ✅ Implemented |
| POST | `/api/v1/generation/embeddings` | **Primary** — text embedding | ✅ Implemented |
| POST | `/api/v1/generation/chat-completions` | Legacy — chat completion | ✅ Active (called by Orchestrator) |
| POST | `/api/v1/generation/summaries` | Legacy — summary generation | ⚠️ Implemented, no callers |
| POST | `/api/v1/generation/proactive-messages` | Legacy — proactive message | ⚠️ Implemented, no callers |

### Health

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/health` | Liveness check | ✅ Implemented |
| GET | `/ready` | Readiness check | 🔶 Stub (always returns ready, no provider health check) |

For detailed request/response schemas, see [API_INTERFACES.md](./API_INTERFACES.md).

---

## Preset Templates

| Template ID | Name | Category | Variables | Note |
|-------------|------|----------|-----------|------|
| `tpl_chat_completion` | Chat Completion | chat | `user_prompt` | Also supports `messages` mode |
| `tpl_memory_compaction` | Memory Compaction Summary | summarization | `user_prompt` | Caller assembles full summarization prompt |
| `tpl_proactive_outreach` | Proactive Outreach Message | proactive | `user_prompt` | Caller assembles full outreach prompt |
| `tpl_sentiment_analysis` | Sentiment Analysis | analysis | `text`, `output_format` (opt) | |
| `tpl_topic_extraction` | Topic Extraction | analysis | `conversation_text` | |
| `tpl_safety_filter` | Safety Content Filter | safety | `content` | |

Business callers can register additional templates via `POST /api/v1/templates`.

---

## Calling Convention for Business Services

All business services should call the unified `POST /api/v1/generation/execute` endpoint. Each use case maps to a preset `template_id`. The caller assembles the full prompt and passes it as the `user_prompt` variable. The AI service provides the system-level prompt (identity, safety, role instructions) via the template.

### Use Case A: Chat Completion (Conversation Orchestrator)

**template_id**: `tpl_chat_completion`

The Conversation Orchestrator can use either **messages mode** (pass full conversation history) or **variable mode** (pass a single assembled prompt). Messages mode is recommended for multi-turn chat.

```python
import httpx

# Option 1: Messages mode (recommended for multi-turn chat)
response = httpx.post("http://localhost:8003/api/v1/generation/execute", json={
    "user_id": "usr_9f2a7c41",
    "conversation_id": "telegram-chat-123456789",
    "template_id": "tpl_chat_completion",
    "messages": [
        {"role": "system", "content": "You are ECHO. The user likes hiking."},
        {"role": "user", "content": "Hey ECHO!"},
        {"role": "assistant", "content": "Hey! How's it going?"},
        {"role": "user", "content": "Any trail suggestions?"}
    ],
    "generation_config": {"temperature": 0.7, "max_tokens": 300},
    "correlation_id": "evt-001"
})

# Option 2: Variable mode (single prompt)
response = httpx.post("http://localhost:8003/api/v1/generation/execute", json={
    "user_id": "usr_9f2a7c41",
    "template_id": "tpl_chat_completion",
    "variables": {"user_prompt": "The user said: 'Any trail suggestions?' — suggest a moderate 2-hour trail."},
    "correlation_id": "evt-001"
})

reply = response.json()["output"][0]["content"]
```

### Use Case B: Memory Compaction Summary (Memory Service)

**template_id**: `tpl_memory_compaction`

The Memory Service assembles the full summarization prompt (including summary type, conversation text, and instructions) and passes it as `user_prompt`.

```python
# The caller assembles the full prompt
conversation_text = "\n".join([
    "[user]: I went for a run this evening.",
    "[assistant]: That's great! How did it go?",
    "[user]: It was good, I ran 5km in the park.",
])
user_prompt = (
    f"Please summarize the following conversation into a compact memory entry.\n"
    f"Summary type: memory_compaction\n\n"
    f"Conversation:\n{conversation_text}\n\n"
    f"Provide a concise summary capturing the user's key preferences, "
    f"emotional state, and important facts."
)

response = httpx.post("http://localhost:8003/api/v1/generation/execute", json={
    "user_id": "usr_9f2a7c41",
    "template_id": "tpl_memory_compaction",
    "variables": {"user_prompt": user_prompt},
    "correlation_id": "evt-022"
})

summary = response.json()["output"][0]["content"]
```

### Use Case C: Proactive Outreach Message (Proactive Engagement Service)

**template_id**: `tpl_proactive_outreach`

The Proactive Engagement Service assembles the full context prompt (relationship tier, affinity, inactivity, tone, user preferences) and passes it as `user_prompt`.

```python
# The caller assembles the full prompt
user_prompt = (
    "Based on the following context, compose a short, natural check-in "
    "message to re-engage this user. The message should feel genuine "
    "and not automated.\n\n"
    "Relationship tier: close_friend\n"
    "Affinity score: 0.74\n"
    "Days since last interaction: 3\n"
    "Desired tone: warm\n"
    "User timezone: Asia/Singapore\n"
    "Recent context about the user: User enjoys evening workouts\n\n"
    "Generate only the message text, nothing else."
)

response = httpx.post("http://localhost:8003/api/v1/generation/execute", json={
    "user_id": "usr_9f2a7c41",
    "template_id": "tpl_proactive_outreach",
    "variables": {"user_prompt": user_prompt},
    "generation_config": {"max_tokens": 120},
    "correlation_id": "evt-6001"
})

message = response.json()["output"][0]["content"]
```

### Response Format (all use cases)

```json
{
  "response_id": "gen-a1b2c3d4e5f6",
  "template_id": "tpl_proactive_outreach",
  "output": [
    {"type": "text", "content": "Hey! It's been a few days — hope your workouts are going well."}
  ],
  "model": "claude-sonnet",
  "usage": {"input_tokens": 156, "output_tokens": 32}
}
```

### Use Case D: Text Embedding (Memory Service / Search)

**Endpoint**: `POST /api/v1/generation/embeddings`

The embedding endpoint generates dense vector representations of text using Amazon Titan Embeddings v2. Used for semantic search, similarity matching, and RAG.

```python
response = httpx.post("http://localhost:8003/api/v1/generation/embeddings", json={
    "user_id": "usr_9f2a7c41",
    "input": "User enjoys evening workouts and friendly check-ins.",
    "correlation_id": "evt-emb-001"
})

embedding = response.json()["embedding"]       # List[float], e.g. 1024-dim vector
dimension = response.json()["dimension"]        # 1024
```

**Response Format**:

```json
{
  "response_id": "gen-a1b2c3d4e5f6",
  "embedding": [0.0123, -0.0456, ...],
  "dimension": 1024,
  "model": "amazon.titan-embed-text-v2:0",
  "usage": {"input_tokens": 12, "output_tokens": 0}
}
```

### Register a Custom Template

Business services can also register custom templates:

```python
response = httpx.post("http://localhost:8003/api/v1/templates", json={
    "name": "Custom Greeting",
    "owner": "conversation-orchestrator",
    "category": "chat",
    "system_prompt": "You are ECHO, a friendly companion.",
    "user_prompt_template": "{{user_prompt}}",
    "variables": {
        "user_prompt": {"type": "string", "required": True, "description": "Full prompt"}
    },
    "defaults": {"temperature": 0.8, "max_tokens": 100}
})
template_id = response.json()["template_id"]
```

---

## Published Events

| Topic | Description | Status |
|-------|-------------|--------|
| `ai.generation.completed` | Emitted for telemetry on successful generation | 🔶 Stub |
| `ai.generation.failed` | Emitted on hard generation failure | 🔶 Stub |

> **Implementation Status**: Events are serialized correctly using Pydantic models, but `EventPublisher._publish()` currently only logs events — no real message broker is connected. Integration with a broker (Redis Streams / RabbitMQ / SQS) is pending infrastructure decisions. See `events/publisher.py`.

---

## Configuration

All configuration is loaded from environment variables with the `AI_GEN_` prefix. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_GEN_HOST` | `0.0.0.0` | Service bind host |
| `AI_GEN_PORT` | `8003` | Service bind port |
| `AI_GEN_PRIMARY_PROVIDER` | `bedrock` | Primary AI provider |
| `AI_GEN_BEDROCK_REGION` | `ap-southeast-1` | AWS region for Bedrock |
| `AI_GEN_BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-4-20250514` | Bedrock model identifier |
| `AI_GEN_BEDROCK_EMBEDDING_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Bedrock embedding model identifier |
| `AI_GEN_BEDROCK_TIMEOUT_SECONDS` | `30` | Request timeout |
| `AI_GEN_EVENT_BROKER_URL` | `redis://localhost:6379/0` | Event broker connection URL |
| `AI_GEN_CONVERSATION_STORE_BASE_URL` | `http://localhost:8010` | Conversation Persistence Store URL |

See `config/settings.py` for the full list of configurable parameters.

---

## Running the Service

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure AWS credentials

The AI Generation Service uses **Amazon Bedrock** (via `boto3`) as its primary AI provider. `boto3` follows the standard [AWS credential resolution chain](https://docs.aws.amazon.com/sdkref/latest/guide/standardized-credentials.html), so how you provide credentials depends on where you run the service.

#### Production (EC2 / ECS / Lambda)

No credential configuration is needed. Attach an **IAM Role** to the EC2 instance, ECS task definition, or Lambda function with the following permissions:

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel"
  ],
  "Resource": [
    "arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-sonnet-4-20250514",
    "arn:aws:bedrock:ap-southeast-1::foundation-model/amazon.titan-embed-text-v2:0"
  ]
}
```

`boto3` automatically retrieves temporary credentials from the instance metadata service (IMDS) or task role. No environment variables need to be set.

#### Local development / debugging

Export your AWS credentials in the terminal before starting the service:

```bash
# Option A: IAM user long-term credentials (not recommended for production)
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="wJal..."
export AWS_DEFAULT_REGION="ap-southeast-1"

# Option B: Temporary credentials from STS (e.g., after `aws sts assume-role`)
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="wJal..."
export AWS_SESSION_TOKEN="FwoG..."
export AWS_DEFAULT_REGION="ap-southeast-1"
```

Alternatively, configure a named profile in `~/.aws/credentials` and set:

```bash
export AWS_PROFILE="your-profile-name"
export AWS_DEFAULT_REGION="ap-southeast-1"
```

> **Tip**: The Bedrock region can also be set via the service config variable `AI_GEN_BEDROCK_REGION` (default: `ap-southeast-1`). This is the region where `boto3` creates the Bedrock Runtime client — it is independent of `AWS_DEFAULT_REGION`.

### 3. Start the service

```bash
uvicorn ai_generation_service.app:app --host 0.0.0.0 --port 8003
```

### 4. Run tests

```bash
# 43 unit tests — no AWS credentials required (providers are mocked)
pytest ai_generation_service/tests/ -v
```

---

## Dependencies on Other Services

| Service | Interface Type | Status |
|---------|---------------|--------|
| Amazon Bedrock | AWS SDK (Converse API + InvokeModel) | ✅ Implemented (`bedrock_provider.py`). Requires boto3 + AWS credentials at deploy time. Converse API for generation, InvokeModel for embeddings |
| Conversation Persistence Store | HTTP API (read messages) | 🔶 Client implemented (`conversation_store_client.py`), target endpoint assumed/unconfirmed |
| Internal Messaging Layer | Event publish | 🔶 Stub — logs only, no broker connected (`events/publisher.py`) |

For details on assumed interfaces, see [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md).

---

## Next Steps (TODO)

| # | Task | Current Status | Dependency | Priority |
|---|------|---------------|------------|----------|
| 1 | Connect event publisher to real broker | Stub (log only) | Infra team to decide broker technology (Redis Streams / RabbitMQ / SQS) | High |
| 2 | Add provider health check to `/ready` | Stub (always returns ready) | None | Medium |
| 3 | Migrate Orchestrator to `/execute` endpoint | Orchestrator still uses `/chat-completions` | Orchestrator team coordination | Medium |
| 4 | Confirm Conversation Store API contract | Client implemented, endpoint assumed | Platform/Data team to confirm endpoint | Medium |
| 5 | Migrate template persistence to shared storage | Local JSON files | Choose storage backend (DynamoDB / MySQL / S3) | Low (single-instance works) |
| 6 | Remove unused legacy endpoints | `/summaries`, `/proactive-messages` have no callers | Confirm no planned callers before removal | Low |
