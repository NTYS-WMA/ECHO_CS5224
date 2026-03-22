# Relationship Service

Standalone FastAPI microservice that tracks affinity scores between users and the ECHO AI companion.

## Overview

Scores are maintained on a **0–1 scale** and map to four relationship tiers:

| Range | Tier |
|---|---|
| 0.00 – 0.30 | Acquaintance |
| 0.31 – 0.60 | Friend |
| 0.61 – 0.80 | Close Friend |
| 0.81 – 1.00 | Best Friend |

Scoring is session-based — GPT-4o evaluates the sentiment of a completed conversation and adjusts the score accordingly. A passive decay of -0.005/day applies to inactive users.

## Architecture

This service connects to the **shared PostgreSQL database** owned by the main application. It:
- **Reads** from `users` and `messages` (owned by other services)
- **Owns** the `relationship_scores`, `score_history` tables (auto-created on startup)

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/relationships/{user_id}/context` | Returns affinity score, tier, and decay state. Called by the orchestrator. |
| PATCH | `/api/v1/relationships/{user_id}/score` | Manually sets the score (admin/testing only). |
| GET | `/health` | Health check. |

## Background Jobs

| Job | Schedule | Description |
|---|---|---|
| `session_score_job` | Every 15 min | Scores completed conversation sessions via GPT-4o |
| `inactivity_decay_job` | Daily at 03:00 UTC | Applies -0.005/day decay to inactive users |

## Database Tables

| Table | Owner | Access |
|---|---|---|
| `users` | Other service | Read-only |
| `messages` | Other service | Read-only |
| `relationship_scores` | This service | Read/Write |
| `score_history` | This service | Write (audit log) |

The `score_history` table records every scoring event with sentiment, delta, new score, and GPT-4o's reasoning — useful for monitoring score changes in production.

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/echo_db
```

### 3. Ensure shared DB tables exist

The `users` and `messages` tables must already exist in the shared database (created by their respective services). The `relationship_scores` and `score_history` tables are created automatically on startup.

For local development, seed a test user:
```sql
CREATE TABLE users (
    id VARCHAR(16) PRIMARY KEY,
    telegram_id BIGINT,
    first_name VARCHAR(128),
    onboarding_complete BOOLEAN DEFAULT FALSE,
    last_active_at TIMESTAMPTZ
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(16) REFERENCES users(id),
    role VARCHAR(16),
    content TEXT,
    is_proactive BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO users (id, first_name, onboarding_complete, last_active_at)
VALUES ('user001', 'Alice', TRUE, NOW() - INTERVAL '1 hour');

INSERT INTO relationship_scores (user_id, score, total_interactions, positive_interactions, negative_interactions)
VALUES ('user001', 0.10, 0, 0, 0);
```

### 4. Run

```bash
python main.py
```

Service starts on port `18089`. API docs available at `http://localhost:18089/docs`.

## Integration Guide for Other Services

### For the User Service

Must create and maintain the `users` table with at least these columns:

```sql
CREATE TABLE users (
    id VARCHAR(16) PRIMARY KEY,
    telegram_id BIGINT,
    first_name VARCHAR(128),
    onboarding_complete BOOLEAN DEFAULT FALSE,
    last_active_at TIMESTAMPTZ
);
```

`last_active_at` must be updated whenever a user sends a message — this is how the relationship service detects session end (30 min of inactivity).

### For the Chat/Message Service

Must create and maintain the `messages` table with at least these columns:

```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(16) REFERENCES users(id),
    role VARCHAR(16),       -- 'user' or 'assistant'
    content TEXT,
    is_proactive BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Set `is_proactive = TRUE` for messages where ECHO initiates contact unprompted — the scoring model treats unanswered proactive messages as a mild negative signal.

### For the AI Service

The relationship service calls the AI service for session scoring. The AI service must expose a single-turn completion endpoint:

```
POST /api/v1/completions
Content-Type: application/json

{
  "prompt": "<session transcript>",
  "max_tokens": 120
}
```

Response:
```json
{
  "text": "<raw model output>"
}
```

The response must return **raw text** (not structured JSON) — the relationship service parses the model output itself.

Once the AI service is ready, replace [services/ai_service.py](services/ai_service.py) with an HTTP client that calls this endpoint. The only contract the rest of this service depends on is:

```python
async def complete(prompt: str, max_tokens: int = 256) -> str
```

### For the Orchestrator Service

Call the relationship context endpoint before building each system prompt:

```
GET http://relationship-service:18089/api/v1/relationships/{user_id}/context
```

Response:
```json
{
  "user_id": "user001",
  "affinity_score": 0.47,
  "tier": "friend",
  "interaction_count": 3,
  "last_interaction_at": "2026-03-22T09:18:30+00:00",
  "decay_state": {
    "last_decay_at": null,
    "days_inactive": 0
  },
  "updated_at": "2026-03-22T09:18:30+00:00"
}
```

Use `tier` and `affinity_score` to personalise the system prompt (e.g. ECHO speaks more warmly to a `best_friend` than an `acquaintance`). Returns `404` if the user has no relationship record yet — treat as `acquaintance` in that case.

### Startup Order

Services must start in this order to avoid FK constraint errors:

1. **User Service** — creates `users` table
2. **Chat/Message Service** — creates `messages` table
3. **Relationship Service** — creates `relationship_scores` and `score_history` tables (references `users`)

---

## Monitoring Score History

Query the full scoring audit log:

```sql
SELECT user_id, delta, new_score, sentiment, intensity, reasoning, reason, scored_at
FROM score_history
WHERE user_id = 'user001'
ORDER BY scored_at DESC;
```

## Testing the Cron Manually

```bash
python -c "
import asyncio, logging
logging.basicConfig(level=logging.INFO)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import get_settings
from managers import relationship_manager

async def test():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        await relationship_manager.run_session_scoring(session)
    await engine.dispose()

asyncio.run(test())
"
```

Reset eligibility before each test run:
```sql
UPDATE relationship_scores SET last_scored_at = NULL WHERE user_id = 'user001';
UPDATE users SET last_active_at = NOW() - INTERVAL '40 minutes' WHERE id = 'user001';
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | required | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model used for session scoring |
| `DATABASE_URL` | required | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `PORT` | `18089` | Service port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `APP_ENV` | `development` | Environment name |
