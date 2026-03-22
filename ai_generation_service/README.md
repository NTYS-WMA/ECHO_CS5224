# AI Generation Service

The AI Generation Service provides model-agnostic text generation capabilities for the ECHO platform. It encapsulates all interactions with foundation models and exposes a clean internal API for conversational reply generation, memory summarization, and proactive outreach message drafting.

---

## Architecture Position

```
Conversation Orchestrator ──▶ AI Generation Service ──▶ Amazon Bedrock (Claude)
Memory Service ─────────────▶ AI Generation Service       │
Proactive Engagement ───────▶ AI Generation Service       ▼
                                                     Fallback Provider (optional)
```

The AI Generation Service sits between the business logic services (Orchestrator, Memory, Proactive Engagement) and the AI model providers. It abstracts away provider-specific details, implements retry and fallback logic, and publishes telemetry events for observability.

---

## Directory Structure

```
ai_generation_service/
├── __init__.py
├── app.py                          # FastAPI application entry point
├── requirements.txt                # Python dependencies
├── API_INTERFACES.md               # API interface reference for callers
├── ASSUMED_INTERFACES.md           # Assumed external interfaces (TO BE UPDATED)
├── README.md                       # This file
├── config/
│   ├── __init__.py
│   └── settings.py                 # Configuration via environment variables
├── models/
│   ├── __init__.py
│   ├── requests.py                 # Request Pydantic models
│   ├── responses.py                # Response Pydantic models
│   └── events.py                   # Event Pydantic models
├── routes/
│   ├── __init__.py
│   ├── generation_routes.py        # /api/v1/generation/* endpoints
│   └── health_routes.py            # /health and /ready endpoints
├── services/
│   ├── __init__.py
│   ├── provider_base.py            # Abstract AI provider interface
│   ├── bedrock_provider.py         # Amazon Bedrock (Claude) provider
│   ├── fallback_provider.py        # OpenAI-compatible fallback provider
│   ├── prompt_builder.py           # Prompt construction for all operations
│   ├── conversation_store_client.py # Client for Conversation Persistence Store
│   └── generation_service.py       # Core business logic with retry/fallback
├── events/
│   ├── __init__.py
│   └── publisher.py                # Event publisher for messaging layer
├── utils/
│   ├── __init__.py
│   └── helpers.py                  # ID generation and utility functions
└── tests/
    ├── __init__.py
    └── test_generation_routes.py   # Unit tests for API routes
```

---

## API Endpoints

| Method | Endpoint                                  | Source                       | Description                    |
|--------|-------------------------------------------|------------------------------|--------------------------------|
| POST   | `/api/v1/generation/chat-completions`     | Conversation Orchestrator    | Generate a conversational reply |
| POST   | `/api/v1/generation/summaries`            | Memory Service               | Generate a conversation summary |
| POST   | `/api/v1/generation/proactive-messages`   | Proactive Engagement Service | Generate a proactive message    |
| GET    | `/health`                                 | Infrastructure               | Liveness check                 |
| GET    | `/ready`                                  | Infrastructure               | Readiness check                |

For detailed request/response schemas, see [API_INTERFACES.md](./API_INTERFACES.md).

---

## Published Events

| Topic                     | Description                                      |
|---------------------------|--------------------------------------------------|
| `ai.generation.failed`    | Emitted on hard generation failure               |
| `ai.generation.completed` | Emitted for telemetry on successful generation   |

---

## Configuration

All configuration is loaded from environment variables with the `AI_GEN_` prefix. Key settings:

| Variable                          | Default                              | Description                        |
|-----------------------------------|--------------------------------------|------------------------------------|
| `AI_GEN_HOST`                     | `0.0.0.0`                           | Service bind host                  |
| `AI_GEN_PORT`                     | `8003`                               | Service bind port                  |
| `AI_GEN_PRIMARY_PROVIDER`         | `bedrock`                            | Primary AI provider                |
| `AI_GEN_BEDROCK_REGION`           | `ap-southeast-1`                     | AWS region for Bedrock             |
| `AI_GEN_BEDROCK_MODEL_ID`         | `anthropic.claude-sonnet-4-20250514` | Bedrock model identifier           |
| `AI_GEN_BEDROCK_TIMEOUT_SECONDS`  | `30`                                 | Request timeout                    |
| `AI_GEN_EVENT_BROKER_URL`         | `redis://localhost:6379/0`           | Event broker connection URL        |
| `AI_GEN_CONVERSATION_STORE_BASE_URL` | `http://localhost:8010`           | Conversation Persistence Store URL |

See `config/settings.py` for the full list of configurable parameters.

---

## Running the Service

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn ai_generation_service.app:app --host 0.0.0.0 --port 8003

# Run tests
pytest ai_generation_service/tests/ -v
```

---

## Dependencies on Other Services

| Service                       | Interface Type     | Status          |
|-------------------------------|--------------------|-----------------|
| Conversation Persistence Store | HTTP API (read)   | TO BE UPDATED   |
| Internal Messaging Layer       | Event publish     | TO BE UPDATED   |
| Amazon Bedrock                 | AWS SDK           | Assumed (AWS)   |

For details on assumed interfaces, see [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md).
