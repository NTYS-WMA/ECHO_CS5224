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

Scoring is session-based — the AI Generation Service evaluates the sentiment of a completed conversation and adjusts the score accordingly. A passive decay of -0.005/day applies to inactive users.

## Architecture

This service has **no direct database connection**. All data access is delegated to the **db-manager service** via its REST API (`/relationship-db/*`). The AI Generation Service is called for session scoring.

```
Orchestrator
    │
    ▼
Relationship Service (port 18089)
    ├── db-manager (port 18087)   ← all DB reads/writes
    └── AI Generation Service (port 8003)  ← session scoring
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/relationships/{user_id}/context` | Returns affinity score, tier, and decay state. Called by the orchestrator. |
| PATCH | `/api/v1/relationships/{user_id}/score` | Manually sets the score (admin/testing only). |
| GET | `/health` | Health check. |

### GET `/api/v1/relationships/{user_id}/context`

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

Returns `404` if the user has no relationship record — treat as `acquaintance` in that case.

### PATCH `/api/v1/relationships/{user_id}/score`

Request body:
```json
{ "score": 0.55 }
```

Score must be between `0.0` and `1.0`.

## Background Jobs

| Job | Schedule | Description |
|---|---|---|
| `session_score_job` | Every 15 min | Scores completed conversation sessions via the AI Generation Service |
| `inactivity_decay_job` | Daily at 03:00 UTC | Applies -0.005/day decay to inactive users |

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
DB_MANAGER_URL=http://localhost:18087
AI_GENERATION_SERVICE_URL=http://localhost:8003
PORT=18089
LOG_LEVEL=INFO
APP_ENV=development
```

### 3. Ensure dependent services are running

- **db-manager** must be running on port `18087` — this service makes all DB calls through it
- **AI Generation Service** must be running on port `8003` — used for session scoring

### 4. Run

```bash
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 18089
```

Or:
```bash
python main.py
```

Service starts on port `18089`. API docs available at `http://localhost:18089/docs`.

## Docker

```bash
docker build -t relationship-service .
docker run -p 18089:18089 \
  -e DB_MANAGER_URL=http://host.docker.internal:18087 \
  -e AI_GENERATION_SERVICE_URL=http://host.docker.internal:8003 \
  relationship-service
```

> On Mac/Windows, use `host.docker.internal` to reach services running on the host. On Linux, use the host's IP.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DB_MANAGER_URL` | `http://localhost:18087` | db-manager service base URL |
| `AI_GENERATION_SERVICE_URL` | `http://localhost:8003` | AI Generation Service base URL |
| `PORT` | `18089` | Service port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `APP_ENV` | `development` | Environment name |

## Integration Guide for Other Services

### For the Orchestrator Service

Call the relationship context endpoint before building each system prompt:

```
GET http://relationship-service:18089/api/v1/relationships/{user_id}/context
```

Use `tier` and `affinity_score` to personalise the system prompt (e.g. ECHO speaks more warmly to a `best_friend` than an `acquaintance`). Returns `404` if no record exists — treat as `acquaintance`.

### For the AI Generation Service

On first scoring call, this service auto-registers a passthrough template named **"Relationship Scoring"** (owner: `relationship-service`). No manual setup needed.

The template accepts one variable `full_prompt` and is called via:
```
POST /api/v1/generation/execute
{
  "user_id": "relationship-service",
  "template_id": "<auto-registered id>",
  "variables": { "full_prompt": "<complete scoring prompt>" },
  "generation_config": { "max_tokens": 1024 }
}
```

A 409 on template registration is handled gracefully — the service looks up the existing template by owner and reuses it.

### For the db-manager Service

This service uses the following db-manager endpoints under the `/relationship-db` prefix:

| Method | Path | Description |
|---|---|---|
| GET | `/relationship-db/users/{user_id}` | Get user by ID |
| GET | `/relationship-db/users/ended-sessions` | Users whose session has ended and not yet scored |
| GET | `/relationship-db/users/inactive` | Users inactive beyond a threshold |
| GET | `/relationship-db/messages` | Messages for a user since a datetime |
| GET | `/relationship-db/scores/{user_id}` | Get relationship score record |
| PUT | `/relationship-db/scores/{user_id}` | Update relationship score |
| POST | `/relationship-db/scores/{user_id}/history` | Insert score history entry |
