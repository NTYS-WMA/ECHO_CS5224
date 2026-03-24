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

| Template ID | Name | Category | Variables |
|-------------|------|----------|-----------|
| `tpl_chat_completion` | Chat Completion | chat | `user_prompt` |
| `tpl_memory_compaction` | Memory Compaction Summary | summarization | `summary_type`, `conversation_text` |
| `tpl_proactive_outreach` | Proactive Outreach Message | proactive | `context_block` |
| `tpl_sentiment_analysis` | Sentiment Analysis | analysis | `text`, `output_format` (opt) |
| `tpl_topic_extraction` | Topic Extraction | analysis | `conversation_text` |
| `tpl_safety_filter` | Safety Content Filter | safety | `content` |

Business callers can register additional templates via `POST /api/v1/templates`.

---

## Usage Example

### 1. Register a Custom Template

```python
import httpx

response = httpx.post("http://localhost:8003/api/v1/templates", json={
    "name": "Custom Greeting",
    "owner": "conversation-orchestrator",
    "category": "chat",
    "system_prompt": "You are ECHO, a friendly companion.",
    "user_prompt_template": "Greet the user: {{context}}",
    "variables": {
        "context": {"type": "string", "required": True, "description": "User context"}
    },
    "defaults": {"temperature": 0.8, "max_tokens": 100}
})
template_id = response.json()["template_id"]
# e.g., "tpl_custom_greeting_a1b2c3"
```

### 2. Execute Generation with Template

```python
response = httpx.post("http://localhost:8003/api/v1/generation/execute", json={
    "user_id": "usr_9f2a7c41",
    "template_id": template_id,
    "variables": {"context": "User likes hiking and morning coffee."}
})
print(response.json()["output"][0]["content"])
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
| `AI_GEN_BEDROCK_TIMEOUT_SECONDS` | `30` | Request timeout |
| `AI_GEN_EVENT_BROKER_URL` | `redis://localhost:6379/0` | Event broker connection URL |
| `AI_GEN_CONVERSATION_STORE_BASE_URL` | `http://localhost:8010` | Conversation Persistence Store URL |

See `config/settings.py` for the full list of configurable parameters.

---

## Running the Service

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn ai_generation_service.app:app --host 0.0.0.0 --port 8003

# Run tests (37 tests)
pytest ai_generation_service/tests/ -v
```

---

## Dependencies on Other Services

| Service | Interface Type | Status |
|---------|---------------|--------|
| Amazon Bedrock | AWS SDK (Converse API) | ✅ Implemented (`bedrock_provider.py`). Requires boto3 + AWS credentials at deploy time |
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
