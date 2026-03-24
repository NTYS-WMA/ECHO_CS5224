# DB Manager (FastAPI)

This module provides a shared data-access foundation for:

- Memory Manager (PostgreSQL + MongoDB)
- Relationship Service (PostgreSQL)

Current scope focuses on:

- PostgreSQL schema/table/index initialization
- MongoDB index initialization
- FastAPI service skeleton for internal health/bootstrap

## Tech Stack

- FastAPI
- PostgreSQL (with `pgvector`)
- MongoDB
- SQLAlchemy async (`asyncpg`)
- Motor (async MongoDB driver)

## Project Layout

```text
db_manager/
  app/
    api/
    core/
    db/
    repositories/
    main.py
  sql/
  .env.example
  requirements.txt
```

## Quick Start

### 0. Start PostgreSQL + MongoDB (Docker)

From `db_manager/`:

```bash
docker compose up -d
```

Stop:

```bash
docker compose down
```

Both services expose default local ports:

- PostgreSQL: `localhost:5432` (`postgres/postgres`, db: `echo_db`)
- MongoDB: `localhost:27017`

1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure env

```bash
copy .env.example .env
```

3. Run service

```bash
uvicorn app.main:app --host 0.0.0.0 --port 18087 --reload
```

4. Verify

- `GET /health/live`
- `GET /health/ready`
- `POST /internal/bootstrap` (manual re-run init)

## PostgreSQL Objects Created

- `memories` (vector memory storage)
- `memory_history` (replacing original SQLite history table)
- `user_profile.user_profile` (basic profile fields extracted from chat)
- `relationship_scores`
- `score_history`

## MongoDB Objects Created

Collection: `user_additional_profile`

Indexes:

- `user_id` unique
- `interests.id`
- `skills.id`
- `personality.id`
