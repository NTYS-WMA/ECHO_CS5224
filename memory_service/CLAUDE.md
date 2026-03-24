# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

If you (Claude) lack sufficient context about this project, please **first read** the following documents:

1. `docs/mem0_integration_analysis.md`

2. `docs/summary_and_challenges.md`

3. `CLAUDE.md`

4. `DEV_GUIDE_UserProfile.md`

5. Conversation records between me and the Claude instance under `discuss/*.md`  
   (You don’t need to read everything — prioritize the most recent and relevant discussions.)

## Communication Requirements

1. All communication during collaboration should be stored in the `discuss` folder at the project root,  
   formatted in Markdown (`.md`).  
   Each file should be sequentially numbered by date or creation time.

2. Once a consensus or decision is reached, **update**:
   - `TODO.md`
   - `DEV_GUIDE_UserProfile.md`
   - and any other affected documents in the root directory.

3. During implementation, always **synchronize updates** to `TODO.md`.  
   If a change involves previously discussed content, confirm with me **before implementing**  
   and then update `DEV_GUIDE_UserProfile.md` accordingly if I approve the change.

4. After completing each development phase, perform a `git commit` with a clear message  
   summarizing what was implemented or changed.

---

### Additional Notes

- If you are uncertain whether a modification affects previous agreements or documents,  
  please ask for confirmation first.
- Use concise, consistent Markdown formatting in all communication files.
- Avoid editing sensitive configuration files (e.g., `.env`) unless explicitly instructed.

## Project Overview

This is a customized Mem0 service that provides memory management capabilities for AI applications. It uses PostgreSQL with pgvector for vector storage, DeepSeek for LLM operations, and Qwen (DashScope) for embeddings. The project is built on top of the mem0ai library with custom modifications for performance monitoring and database configuration.

## Architecture

### Core Components

1. **FastAPI Server** (`server/main.py`): REST API service exposing memory operations
   - Creates, retrieves, searches, updates, and deletes memories
   - Configured via environment variables and DEFAULT_CONFIG
   - Runs on port 18088 (mapped from container port 8000)

2. **Mem0 Library** (`mem0/`): Modified mem0ai library with custom features
   - `mem0/memory/main.py`: Core Memory class with optional performance monitoring
   - `mem0/user_profile/`: **NEW** User profile management module
   - `mem0/embeddings/`: Embedding providers including custom Qwen integration
   - `mem0/vector_stores/`: Vector store implementations (primarily using pgvector)
   - `mem0/llms/`: LLM providers including DeepSeek integration

3. **Performance Monitoring** (`performance_monitoring/`): Optional instrumentation for search operations
   - Tracks timing of embedding generation, database searches, and filtering
   - Enabled via PERFORMANCE_MONITORING_ENABLED flag in mem0/memory/main.py
   - Logs to JSON format for analysis

4. **Database Stack**:
   - PostgreSQL with pgvector extension for vector storage
   - PostgreSQL schema `user_profile` for user basic info **(conversation-extracted, non-authoritative reference data)** (new)
   - MongoDB for user extended profile **(core: interests, skills, personality)** (new)
   - SQLite for history tracking (stored in `./history/history.db`)

### Configuration

The service is configured through environment variables (see `.env.example`):

- **DEEPSEEK_API_KEY**: DeepSeek API for LLM operations
- **DASHSCOPE_API_KEY**: Qwen/DashScope API for embeddings (text-embedding-v4, 1536 dimensions)
- **OPENAI_API_KEY**: Alternative embedding provider (currently not in use)
- **DOUBAO_API_KEY**: Alternative embedding provider (currently not in use)
- **POSTGRES_***: PostgreSQL connection settings
- **MONGODB_URI**: MongoDB connection string (for UserProfile)
- **MONGODB_DATABASE**: MongoDB database name (for UserProfile)
- **HISTORY_DB_PATH**: SQLite database path for history

The main configuration is in `server/main.py` in the `DEFAULT_CONFIG` dictionary (lines 38-81):
- Uses pgvector as vector store provider
- DeepSeek for LLM (model: deepseek-chat)
- Qwen for embeddings (model: text-embedding-v4)
- Graph store is disabled (commented out Neo4j configuration)

## Common Commands

### Development

```bash
# Start all services (PostgreSQL, Mem0 API, SQLite viewer)
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f mem0-service

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Testing

```bash
# Run performance tests (requires service to be running)
python performance_monitoring/test_performance.py

# Test API directly
curl -X POST "http://localhost:18088/memories" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}], "user_id": "test_user"}'
```

### Server (for development without Docker)

```bash
cd server
# Run locally (requires PostgreSQL running separately)
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Service Ports

- **18088**: Mem0 API server (main service)
- **8432**: PostgreSQL (pgvector + user_profile schema)
- **27017**: MongoDB (user additional profile)
- **18089**: SQLite Web viewer (for history database)

## API Endpoints

All endpoints are documented via FastAPI's OpenAPI at http://localhost:18088/docs

Key endpoints:

**Memory endpoints:**
- `POST /memories`: Create memories from messages
- `GET /memories?user_id={id}`: Get all memories for user/agent/run
- `POST /search`: Search memories with query, filters, limit, threshold
- `PUT /memories/{memory_id}`: Update a memory
- `DELETE /memories/{memory_id}`: Delete specific memory
- `DELETE /memories?user_id={id}`: Delete all memories for user/agent/run
- `GET /memories/{memory_id}/history`: Get memory history

**User Profile endpoints (NEW):**
- `POST /profile`: Update user profile from messages
- `GET /profile?user_id={id}&fields={fields}&evidence_limit={n}`: Get user profile (evidence_limit: default 5, -1 for all)
- `GET /profile/missing-fields?user_id={id}&source={pg|mongo|both}`: Get missing profile fields
- `DELETE /profile?user_id={id}`: Delete user profile
- `POST /vocab`: (Reserved, returns 501 Not Implemented)
- `GET /vocab`: (Reserved, returns 501 Not Implemented)

## Key Implementation Details

### Memory Identifiers

The system supports three types of identifiers for scoping memories:
- `user_id`: Memories specific to a user
- `agent_id`: Memories specific to an agent
- `run_id`: Memories specific to a run/session

At least one identifier is required for all operations. Multiple identifiers can be combined.

### Search Functionality

Search endpoint (`server/main.py:168`) accepts:
- `query`: Search text
- `user_id/agent_id/run_id`: Scope filtering
- `filters`: Additional metadata filters
- `limit`: Max results (default 5)
- `threshold`: Minimum similarity score (0.0-1.0)

The actual search implementation is in `mem0/memory/main.py` with vector similarity search via pgvector.

### Performance Monitoring

Performance monitoring is integrated into `mem0/memory/main.py` (lines 46-57) and can be enabled/disabled. When enabled, it instruments:
- Filter building
- Embedding generation
- Vector database searches
- Result formatting

See `performance_monitoring/README.md` for detailed usage.

### Database Switching

The codebase includes test utilities for switching between different database backends:
- `test/database_configs.py`: Configuration templates for different backends
- `test/switch_database.py`: Script to switch between Qdrant, PostgreSQL, etc.

Current production setup uses PostgreSQL with pgvector.

## UserProfile Module (NEW)

### Overview
Automatically extracts and manages user profiles from conversations, including:
- **Basic info** (name, birthday, location, etc.) → PostgreSQL **(Non-authoritative, conversation-extracted reference data only)**
- **Extended info** (interests, skills, personality, social context) → MongoDB **(Core value: deep user characteristics)**

### Core Design
**Evidence-Based**: Every profile update is backed by specific evidence from conversations, stored with timestamps for intelligent conflict resolution.

**Important**: The `basic_info` field stores conversation-extracted basic information for reference purposes only. It is NOT authoritative data. The main service maintains authoritative user information. See `discuss/19-manual_data_decision.md` for architectural decisions.

### Key Features
- **Two-stage LLM Pipeline**: Extract info → Decide updates (ADD/UPDATE/DELETE)
- **Backend Timestamp Generation**: LLM returns evidence text only, backend adds timestamps automatically
- **Smart Conflict Resolution**: LLM analyzes evidence quantity and timing to handle contradictions
- **Unified degree system**: Integer 1-5 for all attributes (interests/skills/personality)
- **Flexible Evidence Retrieval**: Control evidence return with evidence_limit parameter (0/N/-1)

### Documentation
- **Development Guide**: `DEV_GUIDE_UserProfile.md` (complete implementation guide)
- **Architecture Analysis**: `docs/mem0_integration_analysis.md`
- **Design Summary**: `docs/summary_and_challenges.md`
- **Archived Features**: `archived/vocab_design.md` (vocabulary management, future phase)

## Development Notes

- The mem0 library code is a modified version of mem0ai, not the standard pip package
- Graph store functionality (Neo4j) is disabled in current configuration
- The service uses Chinese Aliyun mirror for Qwen embeddings API (dashscope.aliyuncs.com)
- History tracking is separate from vector storage (SQLite vs PostgreSQL)
- Docker Compose includes a sqlite-web container for convenient history database browsing
- **UserProfile module**: Shares LLM with Memory module, uses separate data stores (PostgreSQL + MongoDB)