# My Mem0 Service

### Overview
This repository delivers a production-friendly deployment of [mem0](https://github.com/mem0ai/mem0):
- It preserves **all** upstream long-term memory capabilities (fact extraction, vector storage/search, history tracking).
- A FastAPI layer exposes REST endpoints (`/memories`, `/profile`, etc.), adds logging middleware, and makes the service easy to run inside Docker.
- An evidence-based **UserProfile** module augments the system, persisting conversation-derived basic info in PostgreSQL (non-authoritative reference) and richer attributes in MongoDB.

> 📌 The current profile design is tuned for **children aged 3–9**—a product decision. Schema fields (e.g., school info), prompt examples, and conflict rules prioritise child-centric traits. With light prompt/schema adjustments, the same architecture can serve adult personas.

### Key Components
- **FastAPI server** (`server/main.py`): wraps `mem0.Memory` and `mem0.user_profile.UserProfile`, exposes configuration & CRUD/search endpoints, and wires in request logging middleware.
- **Custom mem0 fork** (`mem0/`): keeps upstream modules while adding user-profile logic, Postgres/Mongo managers, prompt templates, and optional performance hooks.
- **Database tooling** (`scripts/`): SQL bootstrap for the `user_profile` schema, incremental migrations, and a MongoDB initialiser creating collections/indexes.
- **Performance monitoring** (`performance_monitoring/`): opt-in instrumentation controlled from `mem0/memory/main.py`.
- **Documentation**: `DEV_GUIDE_UserProfile.md`, `docs/`, and `CLAUDE.md` capture design choices, requirements, and collaboration rules.

### Configurability Highlights
- `DEFAULT_CONFIG` mirrors `mem0.configs.base.MemoryConfig`. Environment variables feed the structure but you can:
  - Override any provider/model/connection via `.env`/Docker vars.
  - Replace the active config at runtime with `POST /configure`.
  - Embed the library elsewhere with `UserProfile(Memory.from_config(custom_config).config)`.
- DeepSeek + Qwen are default dependencies inside the reference image; swap them freely for other LLM/embedding/vector backends.
- SQLite history storage (`HISTORY_DB_PATH`) can point to any accessible location.

### Child-Focused Profile Design
- PostgreSQL schema ships with `school_name`, `grade`, `class_name`, etc., to capture primary-school context.
- Prompts instruct the LLM to reason about child interests/skills (drawing, reading, etc.).
- Mongo `social_context` assumes the persona is the child, elevating parents/guardians as core relations.
- See `DEV_GUIDE_UserProfile.md` and `scripts/migrations/` for the exact field lists and guidance on adapting them for adult users.

### Quick Deploy (Docker Compose)
Prerequisites: Docker 24+, Compose Plugin 2.20+.

1. **Clone & configure**
   ```bash
   git clone <repo>
   cd my_mem0
   cp .env.example .env
   # edit .env with API keys and DB credentials
   ```

2. **Bootstrap databases** – `docker compose up` will *not* auto-create schemas/indexes:
   ```bash
   docker compose up -d postgres mongodb

   docker compose exec -T postgres \
     psql -U postgres -d postgres -f /app/scripts/init_userprofile_db.sql

   for file in scripts/migrations/*.sql; do
     docker compose exec -T postgres \
       psql -U postgres -d postgres -f "/app/$file"
   done

   MONGODB_URI="mongodb://mongo:mongo@localhost:27017/" \
   MONGODB_DATABASE=mem0 \
   python scripts/init_mongodb.py
   ```

   Existing pgvector volumes (`my_mem0_postgres_db`, etc.) will skip entrypoint scripts—run the SQL manually before starting the API. `UserProfile.initialize_databases()` offers the same logic programmatically.

3. **Launch services**
   ```bash
   docker compose up -d
   docker compose ps
   docker compose logs -f mem0-service
   ```

   Port map: `18088` (API), `8432` (Postgres), `27017` (Mongo), `18089` (SQLite viewer). Data persists in Docker named volumes; swap to bind mounts if you need host-level paths.

4. **Smoke test**
   - Swagger: <http://localhost:18088/docs>
   - Add a memory:
     ```bash
     curl -X POST http://localhost:18088/memories \
       -H 'Content-Type: application/json' \
       -d '{"messages":[{"role":"user","content":"I love dinosaurs"}],"user_id":"demo"}'
     ```
   - Update profile:
     ```bash
     curl -X POST http://localhost:18088/profile \
       -H 'Content-Type: application/json' \
       -d '{"user_id":"demo","messages":[{"role":"user","content":"My name is Lily and I go to school in Beijing"}]}'
     ```

### Running Without Docker
- Install dependencies: `pip install -r server/requirements.txt` (strip `mem0ai`), then `pip install -e .` to expose the local `mem0/` package.
- Provide Postgres + pgvector, MongoDB, and an SQLite path via environment variables.
- Launch FastAPI from `server/`: `uvicorn main:app --host 0.0.0.0 --port 8000`.
- Use the same SQL/Python scripts (or `UserProfile.initialize_databases()`) to create schemas before accepting traffic.

### API Surface
| Endpoint | Description |
| --- | --- |
| `POST /configure` | Swap the active `MemoryConfig` at runtime. |
| `POST /memories` | Add memories; requires one of `user_id`/`agent_id`/`run_id`. |
| `GET /memories`, `GET /memories/{id}` | Retrieve scoped or single memories. |
| `POST /search` | Vector search with filters/threshold/limit. |
| `PUT /memories/{id}`, `DELETE /memories/{id}`, `DELETE /memories` | Update/delete memories. |
| `GET /memories/{id}/history` | Inspect memory history (SQLite). |
| `POST /profile` | Two-stage profile update with optional `manual_data`. |
| `GET /profile` | Query profile data with field filters and `evidence_limit`. |
| `GET /profile/missing-fields` | Suggest missing fields (Postgres/Mongo/both). |
| `DELETE /profile` | Remove profile records from both stores. |
| `POST/GET /vocab` | Reserved (returns HTTP 501). |

### Operations & Troubleshooting
- **Logging**: controlled via `LOG_LEVEL`; request/response logging is provided by `RequestLoggingMiddleware`.
- **Performance monitoring**: toggle `PERFORMANCE_MONITORING_ENABLED` in `mem0/memory/main.py`.
- **JSON safeguards**: the profile pipeline handles retries, JSON cleaning, and per-field fallbacks (`profile_manager.py`).
- **Schema management**: migrations live under `scripts/migrations/`, all idempotent (`IF NOT EXISTS`).
- **Provider changes**: update `.env` or call `POST /configure`; ensure Docker images include the necessary SDKs.

### Further Reading
- [DEV_GUIDE_UserProfile.md](DEV_GUIDE_UserProfile.md) – implementation, prompts, and test strategy.
- [docs/summary_and_challenges.md](docs/summary_and_challenges.md) – design summary & risk log.
- [docs/mem0_integration_analysis.md](docs/mem0_integration_analysis.md) – integration analysis.
- [CLAUDE.md](CLAUDE.md) – collaboration norms.

Use this README for deployment/operations. For code-level changes or schema adjustments, consult the detailed documents before editing.
