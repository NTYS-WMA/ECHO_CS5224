# ECHO — Channel Gateway & Conversation Orchestrator

## What This Does

This branch contains the **Channel Gateway** and **Conversation Orchestrator** — the two services that handle the core message flow for the ECHO chatbot.

When a user sends a message on Telegram:

1. **Channel Gateway** receives the Telegram webhook, validates it, converts it into our internal event format, and publishes it to the event bus
2. **Conversation Orchestrator** picks up the event, gathers context from all other services (profile, relationship, memory), sends everything to the AI service to generate a reply, saves the conversation, and publishes the reply as an outbound event
3. **Channel Gateway** (outbound worker) picks up the reply event and delivers it back to Telegram

All calls to other team members' services (AI, Memory, Relationship, User Profile) go through thin HTTP client wrappers. Right now these return mock data so the full pipeline can be tested without any other services running.

## Setup (Step by Step)

### 1. Clone and install

```bash
git clone <repo-url>
cd echo-orchestrator
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set the Telegram bot token:

```
TELEGRAM_BOT_TOKEN=8705286348:AAGlJArp2fWNS4AIsljwOS_V0O0RBzCEUfw
```

Leave `MOCK_SERVICES=true` for now — this means all downstream service calls return fake data so you can test independently.

### 3. Start the server

```bash
python main.py
```

You should see:

```
ECHO starting up
  Mock services: True
  Telegram token: SET
All workers registered. Active topics: ['conversation.message.received', 'conversation.outbound']
Uvicorn running on http://0.0.0.0:8000
```

### 4. Test locally (no Telegram needed)

Open your browser and go to:

```
http://localhost:8000/docs
```

This opens the Swagger UI where you can try all endpoints. To test the full orchestration pipeline:

1. Find **POST /debug/simulate** and click "Try it out"
2. Leave defaults (`user_id`: `usr_test001`, `text`: `Hello ECHO`) and click Execute
3. You should get back `{"status": "published", "event_id": "evt-..."}`
4. Check your server terminal — you'll see the full orchestration flow logged

Other useful endpoints to try:

- **GET /health** — check the server is running
- **GET /debug/event-bus** — see which event topics have subscribers
- **GET /debug/conversations** — see all conversation state stored in memory

### 5. Test with Telegram (via ngrok)

Since Telegram needs to reach your server over the internet, use ngrok to create a tunnel:

```bash
# Install ngrok from https://ngrok.com/download, then:
ngrok http 8000 --request-header-add "ngrok-skip-browser-warning:true"
```

The `--request-header-add` flag is important — without it, ngrok's free tier shows a browser warning page that blocks Telegram's webhook calls.

You'll see output like:

```
Forwarding    https://some-random-name.ngrok-free.dev -> http://localhost:8000
```

Now set the Telegram webhook (replace the ngrok URL with yours):

```bash
curl -X POST "https://api.telegram.org/bot8705286348:AAGlJArp2fWNS4AIsljwOS_V0O0RBzCEUfw/setWebhook?url=https://YOUR-NGROK-URL.ngrok-free.dev/api/v1/channels/telegram/webhook"
```

You should get:

```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

To verify the webhook is working:

```bash
curl "https://api.telegram.org/bot8705286348:AAGlJArp2fWNS4AIsljwOS_V0O0RBzCEUfw/getWebhookInfo"
```

Now open Telegram, find **@your_friendly_echo_bot**, press Start, and send a message. The bot should reply.

### 6. If Telegram isn't responding

Check these things in order:

1. **Server terminal** — do you see any new log lines when you send a message?
2. **ngrok web UI** at `http://127.0.0.1:4040` — do you see incoming requests?
3. **getWebhookInfo** — does the URL match your current ngrok URL? (ngrok URL changes every restart on the free tier, so you need to set the webhook again each time)
4. **ngrok flag** — make sure you started ngrok with `--request-header-add "ngrok-skip-browser-warning:true"`

## How the Code Works

### Message Flow

```
Telegram User
    │
    ▼
Channel Gateway (webhook.py)
    │  Validates, normalizes Telegram payload
    │  Publishes conversation.message.received
    ▼
Event Bus (event_bus.py)
    │
    ▼
Orchestrator (orchestration_worker.py)
    │  1. Saves user message
    │  2. Fetches profile, relationship, memory context (parallel)
    │  3. Builds system prompt with all context
    │  4. Calls AI generation
    │  5. Saves assistant reply
    │  6. Publishes conversation.outbound
    │  7. Publishes relationship.interaction.recorded
    │  8. Writes memories (background)
    ▼
Event Bus
    │
    ▼
Outbound Worker (outbound_worker.py)
    │  Extracts chat ID, calls Telegram sendMessage API
    ▼
Telegram User (sees the reply)
```

### Event Bus

The event bus (`shared/events/event_bus.py`) is a real in-process async pub/sub system using Python's asyncio. It is NOT mocked. When something publishes an event, all subscribers get called immediately. This is the "Internal Asynchronous Messaging Layer" from the architecture doc, implemented for single-EC2 deployment.

### What Is Mocked vs Real

When `MOCK_SERVICES=true`:

| Component | Mocked? | Details |
|-----------|---------|---------|
| Channel Gateway (webhook) | ❌ Real | Parses actual Telegram payloads |
| Event Bus | ❌ Real | Real async pub/sub, not faked |
| Orchestrator logic | ❌ Real | Full coordination flow runs |
| System prompt builder | ❌ Real | Assembles context into LLM prompt |
| Outbound Worker | ❌ Real | Makes actual Telegram API calls |
| User Profile client | ✅ Mocked | Returns fake profile (name, timezone, preferences) |
| Relationship client | ✅ Mocked | Returns fake affinity score and tier |
| Memory client | ✅ Mocked | Returns fake short-term and long-term memories |
| AI Generation client | ✅ Mocked | Returns echo-style reply instead of calling Claude |
| Conversation Store client | Partial | Always stores in memory; real mode also calls the DB service |

The mock data lives inside each client file in `orchestrator/clients/`. Each function checks `if settings.mock_services` and returns fake data or makes a real HTTP call.

When your teammates' services are running, set `MOCK_SERVICES=false` and update the service URLs in `.env`.

## Project Structure

```
echo-orchestrator/
├── main.py                              # FastAPI entrypoint, wires everything together
├── requirements.txt
├── .env.example                         # Template — copy to .env
│
├── shared/                              # Shared infrastructure
│   ├── config/settings.py               # Pydantic settings loaded from .env
│   ├── events/
│   │   ├── event_bus.py                 # In-process async pub/sub (real, not mocked)
│   │   └── topics.py                    # All topic name constants
│   └── models/
│       └── events.py                    # Pydantic schemas for all events
│
├── channel_gateway/                     # Channel Gateway Service
│   ├── api/webhook.py                   # POST /api/v1/channels/telegram/webhook
│   ├── workers/outbound_worker.py       # Subscribes to conversation.outbound → Telegram
│   └── models/telegram.py              # Telegram payload parsing models
│
├── orchestrator/                        # Conversation Orchestrator Service
│   ├── workers/orchestration_worker.py  # The brain — full pipeline
│   ├── clients/                         # HTTP callers to other teams' services
│   │   ├── user_profile_client.py       # Calls User Profile Service
│   │   ├── memory_client.py             # Calls Memory Service (MyMem0 on :18088)
│   │   ├── relationship_client.py       # Calls Relationship Service
│   │   ├── ai_generation_client.py      # Calls AI Generation Service
│   │   └── conversation_store_client.py # Calls Conversation Persistence Store
│   └── models/context.py               # Internal context assembly models
│
└── tests/
    ├── test_in_process.py               # Full test suite (16 tests)
    ├── sample_telegram_webhook.json     # Sample Telegram payload
    └── sample_payloads.json             # Various test scenarios
```

## Integration Points for Other Teams

This is how the orchestrator connects to your services. Right now these are mocked — when your service is running, we update the URL in `.env` and set `MOCK_SERVICES=false`.

| Your Service | What We Call | Endpoint | Client File |
|---|---|---|---|
| Memory Service (MyMem0) | Semantic search for long-term memories | `POST /search` on `:18088` | `memory_client.py` |
| Memory Service (MyMem0) | Write new memories from conversation | `POST /memories` on `:18088` | `memory_client.py` |
| Memory Service (MyMem0) | Extract/update user profile | `POST /profile` on `:18088` | `memory_client.py` |
| AI Generation Service | Chat completion for reply generation | `POST /api/v1/generation/chat-completions` | `ai_generation_client.py` |
| Relationship Service | Get affinity score and tier | `GET /api/v1/relationships/{user_id}/context` | `relationship_client.py` |
| User Profile Service | Get user profile and preferences | `GET /api/v1/users/{user_id}/profile` | `user_profile_client.py` |
| Conversation Store | Persist message history | `POST /api/v1/conversations/{conversation_id}/messages` | `conversation_store_client.py` |

### Events We Publish (your service may consume these)

| Topic | When | Payload summary |
|---|---|---|
| `conversation.outbound` | After AI generates a reply | Contains reply text, user ID, conversation ID |
| `relationship.interaction.recorded` | After each user interaction | User ID, conversation ID, sentiment, timestamp |
| `memory.summary.requested` | When conversation hits length threshold | User ID, conversation ID, message window |
| `conversation.processing.failed` | When orchestration fails | Stage, error code, retryable flag |

### Events We Consume

| Topic | Published By | What We Do |
|---|---|---|
| `conversation.message.received` | Channel Gateway | Orchestrator starts the reply pipeline |
| `conversation.outbound` | Orchestrator | Outbound Worker delivers to Telegram |

## Running Tests

```bash
cd echo-orchestrator
python tests/test_in_process.py
```

This runs 16 tests covering the webhook, orchestrator, prompt builder, event models, mock clients, and full pipeline. No external services needed.

## Notes

- The Relationship Service uses session-based scoring (15-min scheduler cycle), not per-message. We publish `relationship.interaction.recorded` events and they process them on their schedule.
- The ngrok URL changes every time you restart ngrok on the free tier. You need to set the webhook again each time.
- The `.env` file is gitignored — the bot token won't be committed. Only `.env.example` (with placeholder values) is in the repo.
- The system prompt adapts based on relationship tier — ECHO talks differently to an acquaintance vs a best friend.
