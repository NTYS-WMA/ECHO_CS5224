# Memory Service (MyMem0) — Internal Integration Guide

**Version**: 1.0
**Last Updated**: 2026-03-17
**Maintained by**: Memory Service Team

---

## Table of Contents

1. [Service Overview](#1-service-overview)
2. [Access Information](#2-access-information)
3. [Data Models](#3-data-models)
4. [API Reference](#4-api-reference)
   - [Memory APIs](#41-memory-apis)
   - [User Profile APIs](#42-user-profile-apis)
5. [Database Schemas](#5-database-schemas)
   - [PostgreSQL — Vector Store](#51-postgresql--vector-store-public-schema)
   - [PostgreSQL — User Basic Info](#52-postgresql--user-basic-info-user_profile-schema)
   - [MongoDB — User Extended Profile](#53-mongodb--user-extended-profile)
   - [SQLite — Memory History](#54-sqlite--memory-history)
6. [AI Service Dependencies](#6-ai-service-dependencies)
7. [Error Handling](#7-error-handling)
8. [Constraints & Notes](#8-constraints--notes)

---

## 1. Service Overview

Position of the Memory Service (MyMem0) within the broader microservice architecture:

```
Master Service
  ├──▶ Memory Service (this service)  ◀── described in this document
  ├──▶ AI Service
  ├──▶ DB Service
  └──▶ Other Services
```

**Responsibilities**:

- Store and retrieve semantic memories extracted from conversations (vector storage with similarity search)
- Automatically extract and maintain user profiles from conversations (basic info + deep characteristics such as interests, skills, and personality)

**Out of scope**:

- Authentication / authorization (caller's responsibility; this service has no auth implemented yet)
- Authoritative user basic info (owned by the Master Service / DB Service; `basic_info` in this service is conversation-extracted reference data only)

---

## 2. Access Information

**Base URL** (internal network):

```
http://<host>:18088
```

| Port  | Purpose                              |
|-------|--------------------------------------|
| 18088 | Memory Service main API (this doc)   |
| 8432  | PostgreSQL (internal, do not connect directly) |
| 27017 | MongoDB (internal, do not connect directly)    |

**Protocol**: HTTP/1.1, JSON request and response bodies, `Content-Type: application/json`.

**Interactive Docs**: `http://<host>:18088/docs` (Swagger UI)

---

## 3. Data Models

### 3.1 Message

All write endpoints accept a list of messages in this format:

```json
{
  "role": "user",        // "user" | "assistant"
  "content": "message text here"
}
```

### 3.2 Memory Item

A single memory entry as returned by read endpoints:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",  // UUID
  "memory": "User likes playing football",         // distilled memory text
  "hash": "abc123...",                             // content hash for deduplication
  "created_at": "2026-03-10T08:00:00.000Z",        // ISO 8601
  "updated_at": "2026-03-15T10:30:00.000Z",
  "user_id": "user_001",                           // at least one scope field present
  "agent_id": "agent_001",                         // optional
  "run_id": "run_001",                             // optional
  "actor_id": "user_001",                          // optional, message sender ID
  "role": "user",                                  // optional, message role
  "metadata": {}                                   // optional, caller-supplied custom metadata
}
```

### 3.3 UserProfile

Full response structure of `GET /profile`:

```json
{
  "user_id": "user_001",
  "basic_info": {
    "name": "Zhang San",
    "nickname": "Xiao Zhang",
    "english_name": "John",
    "birthday": "2016-05-20",
    "gender": "male",
    "nationality": "Chinese",
    "hometown": "Chengdu",
    "current_city": "Beijing",
    "timezone": "Asia/Shanghai",
    "language": "zh-CN",
    "school_name": "Beijing Experimental Primary School",
    "grade": "Grade 3",
    "class_name": "Class 2"
  },
  "additional_profile": {
    "interests": [
      {
        "id": "interest_abc123",
        "name": "Football",
        "degree": 4,
        "evidence": [
          {"text": "Goes to play football every weekend and really enjoys it", "timestamp": "2026-03-10T08:00:00.000Z"}
        ]
      }
    ],
    "skills": [
      {
        "id": "skill_def456",
        "name": "Drawing",
        "degree": 3,
        "evidence": [
          {"text": "Won a prize at the school art competition", "timestamp": "2026-03-12T10:00:00.000Z"}
        ]
      }
    ],
    "personality": [
      {
        "id": "pers_ghi789",
        "name": "Outgoing",
        "degree": 4,
        "evidence": [
          {"text": "Loves hanging out and playing with classmates", "timestamp": "2026-03-10T08:00:00.000Z"}
        ]
      }
    ],
    "social_context": {
      "family": {
        "father": {"name": "Zhang Ming", "info": ["Engineer", "likes basketball"]},
        "mother": {"name": "Li Hua", "info": ["Teacher"]},
        "brother": [{"name": "Xiao Di", "info": ["5 years old"]}],
        "sister": []
      },
      "friends": [
        {"name": "Xiao Ming", "info": ["classmate", "likes football"]}
      ],
      "others": [
        {"name": null, "relation": "math teacher", "info": ["strict but patient"]}
      ]
    },
    "learning_preferences": {
      "preferred_time": "evening",
      "preferred_style": "visual",
      "difficulty_level": "intermediate"
    }
  }
}
```

**`degree` semantics** (integer 1–5):

| Field         | Meaning                                         |
|---------------|-------------------------------------------------|
| `interests`   | Level of liking (1 = mild, 5 = passionate)      |
| `skills`      | Proficiency (1 = beginner, 5 = expert)          |
| `personality` | Trait strength (1 = occasional, 5 = very strong)|

**`social_context` structure**:

| Field     | Type   | Description                                                  |
|-----------|--------|--------------------------------------------------------------|
| `family`  | object | Direct relatives; key is the relationship identifier (see table below) |
| `friends` | array  | Friend list; each item has `name` + `info`                   |
| `others`  | array  | Other relationships; each item has `name` + `relation` + `info` |

Supported `family` keys:

| Singular (object)                                                              | Plural (array)                                                     |
|--------------------------------------------------------------------------------|--------------------------------------------------------------------|
| `father`, `mother`, `spouse`                                                   | `brother[]`, `sister[]`, `son[]`, `daughter[]`, `grandson[]`, `granddaughter[]` |
| `grandfather_paternal`, `grandmother_paternal`                                 | —                                                                  |
| `grandfather_maternal`, `grandmother_maternal`                                 | —                                                                  |

> Collateral relatives (uncle, aunt, cousin, etc.) go into `others` with an explicit `relation` field to distinguish e.g. "paternal uncle" vs "maternal uncle".

---

## 4. API Reference

### 4.1 Memory APIs

---

#### `POST /memories` — Write Memories

Extracts facts from conversation messages and stores them in the memory store. The LLM automatically decides whether to ADD, UPDATE, or DELETE existing memories.

**Request body**:

```json
{
  "messages": [
    {"role": "user", "content": "My name is Zhang San, I live in Beijing, and I recently started learning piano."},
    {"role": "assistant", "content": "That's great, learning piano is fun!"}
  ],
  "user_id": "user_001",          // at least one of user_id / agent_id / run_id required
  "agent_id": null,
  "run_id": null,
  "metadata": {"source": "chat"} // optional, custom metadata stored with memories
}
```

**Response** `200 OK`:

```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "memory": "User's name is Zhang San and lives in Beijing",
      "event": "ADD"
    },
    {
      "id": "661f9511-f30c-52e5-b827-557766551111",
      "memory": "User recently started learning piano",
      "event": "ADD"
    },
    {
      "id": "772a0622-g41d-63f6-c938-668877662222",
      "memory": "User is interested in music",
      "event": "UPDATE",
      "previous_memory": "User has some interest in music"
    }
  ]
}
```

`event` enum: `ADD` | `UPDATE` | `DELETE`

---

#### `GET /memories` — List All Memories

**Query parameters**:

| Parameter  | Type   | Required | Description                           |
|------------|--------|----------|---------------------------------------|
| `user_id`  | string | *        | At least one of the three is required |
| `agent_id` | string | *        | Same                                  |
| `run_id`   | string | *        | Same                                  |

**Response** `200 OK`:

```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "memory": "User's name is Zhang San and lives in Beijing",
      "hash": "d41d8cd98f00b204...",
      "created_at": "2026-03-10T08:00:00.000Z",
      "updated_at": "2026-03-10T08:00:00.000Z",
      "user_id": "user_001"
    }
  ]
}
```

---

#### `GET /memories/{memory_id}` — Get a Single Memory

**Path parameter**: `memory_id` (UUID)

**Response** `200 OK`: A single Memory Item object (same structure as above).

---

#### `PUT /memories/{memory_id}` — Update a Memory

Directly overwrites the memory text (bypasses LLM).

**Path parameter**: `memory_id` (UUID)

**Request body**:

```json
{
  "memory": "Updated memory text content"
}
```

**Response** `200 OK`:

```json
{"message": "Memory updated successfully"}
```

---

#### `DELETE /memories/{memory_id}` — Delete a Single Memory

**Path parameter**: `memory_id` (UUID)

**Response** `200 OK`:

```json
{"message": "Memory deleted successfully"}
```

---

#### `DELETE /memories` — Delete All Memories for a Scope

**Query parameters**: `user_id` / `agent_id` / `run_id` (at least one)

**Response** `200 OK`:

```json
{"message": "All relevant memories deleted"}
```

---

#### `POST /search` — Semantic Memory Search

Performs vector similarity search over the memory store and returns the most relevant results.

**Request body**:

```json
{
  "query": "user's music hobbies",
  "user_id": "user_001",           // at least one scope required
  "agent_id": null,
  "run_id": null,
  "filters": {"source": "chat"},   // optional, filter by metadata fields
  "limit": 5,                      // default 5
  "threshold": 0.3                 // optional, minimum similarity score (0.0–1.0)
}
```

**Response** `200 OK`:

```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "memory": "User recently started learning piano",
      "score": 0.87,
      "hash": "abc123...",
      "created_at": "2026-03-10T08:00:00.000Z",
      "updated_at": "2026-03-10T08:00:00.000Z",
      "user_id": "user_001"
    }
  ]
}
```

> `score` is cosine similarity; higher is more relevant. Set `threshold` to filter out low-relevance results.

---

#### `GET /memories/{memory_id}/history` — Memory Change History

Returns the full modification history of a memory entry.

**Response** `200 OK`:

```json
[
  {
    "id": "history-uuid",
    "memory_id": "550e8400-e29b-41d4-a716-446655440000",
    "old_memory": null,
    "new_memory": "User recently started learning piano",
    "event": "ADD",
    "created_at": "2026-03-10T08:00:00.000Z",
    "updated_at": "2026-03-10T08:00:00.000Z",
    "is_deleted": false,
    "actor_id": null,
    "role": "user"
  }
]
```

`event` enum: `ADD` | `UPDATE` | `DELETE`

---

### 4.2 User Profile APIs

---

#### `POST /profile` — Extract and Update User Profile

Analyzes conversation messages to extract user profile data and updates both basic info (PostgreSQL) and extended profile (MongoDB). Internally makes two sequential LLM calls: extraction first, then update decision.

**Request body**:

```json
{
  "messages": [
    {"role": "user", "content": "My name is Li Ming, I live in Shanghai, and I've been really into photography lately."},
    {"role": "assistant", "content": "Photography is fun! What subjects do you like to shoot?"},
    {"role": "user", "content": "I love shooting landscapes. I go out every weekend to take photos."}
  ],
  "user_id": "user_001"  // required
}
```

**Response** `200 OK`:

```json
{
  "success": true,
  "basic_info_updated": true,
  "additional_profile_updated": true,
  "operations_performed": {
    "added": 2,
    "updated": 0,
    "deleted": 0
  },
  "errors": []
}
```

On failure:

```json
{
  "success": false,
  "error": "error description"
}
```

---

#### `GET /profile` — Get User Profile

**Query parameters**:

| Parameter        | Type    | Required | Default | Description                                                                   |
|------------------|---------|----------|---------|-------------------------------------------------------------------------------|
| `user_id`        | string  | yes      | —       | User ID                                                                       |
| `fields`         | string  | no       | all     | Comma-separated field names from `additional_profile`, e.g. `interests,skills` |
| `evidence_limit` | integer | no       | 5       | `0` = no evidence, `N` = latest N items, `-1` = all evidence                 |

**Response** `200 OK`: See [3.3 UserProfile structure](#33-userprofile).

> If the user does not exist and PalServer is configured, the service will attempt a cold-start import from PalServer before returning.

---

#### `GET /profile/missing-fields` — Get Missing Profile Fields

Returns which profile fields have not yet been populated. Useful for proactively gathering information.

**Query parameters**:

| Parameter | Type   | Required | Default | Description                                     |
|-----------|--------|----------|---------|-------------------------------------------------|
| `user_id` | string | yes      | —       | User ID                                         |
| `source`  | string | no       | `both`  | `pg` (basic info) / `mongo` (extended profile) / `both` |

**Response** `200 OK`:

```json
{
  "user_id": "user_001",
  "missing_fields": {
    "basic_info": ["hometown", "gender", "birthday"],
    "additional_profile": ["personality", "learning_preferences"]
  }
}
```

---

#### `DELETE /profile` — Delete User Profile

**Query parameter**: `user_id` (required)

**Response** `200 OK`:

```json
{
  "success": true,
  "basic_info_deleted": true,
  "additional_profile_deleted": false
}
```

> `false` means the user had no data in that particular store (not an error).

---

#### `POST /vocab` and `GET /vocab` — Vocabulary Management (Not Implemented)

Reserved endpoints. Currently return `501 Not Implemented`. Planned for Phase 2.

---

## 5. Database Schemas

> The following describes internal storage structures for reference during troubleshooting and data flow analysis. Callers should not connect to these databases directly.

### 5.1 PostgreSQL — Vector Store (`public` schema)

Table name: configured via `POSTGRES_COLLECTION` env var, defaults to `memories`.

```sql
CREATE TABLE memories (
    id      UUID PRIMARY KEY,
    vector  vector(1536),   -- Qwen text-embedding-v4 vectors, 1536 dimensions
    payload JSONB           -- memory data and metadata
);

-- HNSW index for fast approximate nearest-neighbor search
CREATE INDEX memories_hnsw_idx ON memories USING hnsw (vector vector_cosine_ops);
```

`payload` JSONB structure:

```json
{
  "data": "User's name is Zhang San and lives in Beijing",
  "hash": "md5_hash_string",
  "created_at": "2026-03-10T08:00:00.000Z",
  "updated_at": "2026-03-10T08:00:00.000Z",
  "user_id": "user_001",
  "agent_id": "agent_001",   // optional
  "run_id": "run_001",       // optional
  "actor_id": "user_001",    // optional
  "role": "user"             // optional
}
```

---

### 5.2 PostgreSQL — User Basic Info (`user_profile` schema)

Table: `user_profile.user_profile`

> **Important**: This table stores basic info extracted from conversations. It is **non-authoritative reference data** for AI personalization only. The authoritative user record is maintained by the Master Service / DB Service.

```sql
CREATE TABLE user_profile.user_profile (
    user_id       VARCHAR(50)  PRIMARY KEY,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Basic info
    name          VARCHAR(100),   -- full name
    nickname      VARCHAR(100),   -- preferred name / nickname
    english_name  VARCHAR(100),   -- English name
    birthday      DATE,           -- date of birth
    gender        VARCHAR(10),    -- male / female / unknown
    nationality   VARCHAR(50),    -- e.g. Chinese
    hometown      VARCHAR(100),   -- hometown
    current_city  VARCHAR(100),   -- current city of residence
    timezone      VARCHAR(50),    -- e.g. Asia/Shanghai
    language      VARCHAR(50),    -- e.g. zh-CN, en-US

    -- Education fields (targeted at children aged 3–9)
    school_name   VARCHAR(200),   -- school name
    grade         VARCHAR(50),    -- e.g. Grade 3 / 三年级
    class_name    VARCHAR(50)     -- e.g. Class 2A / 2班 (optional)
);
```

---

### 5.3 MongoDB — User Extended Profile

Database: configured via `MONGODB_DATABASE`
Collection: `user_additional_profile`

One document per user:

```json
{
  "user_id": "user_001",

  "interests": [
    {
      "id": "interest_abc123",
      "name": "Football",
      "degree": 4,
      "evidence": [
        {"text": "Goes to play football every weekend", "timestamp": "2026-03-10T08:00:00.000Z"}
      ]
    }
  ],

  "skills": [
    {
      "id": "skill_def456",
      "name": "Drawing",
      "degree": 3,
      "evidence": [
        {"text": "Won a prize at the school art competition", "timestamp": "2026-03-12T10:00:00.000Z"}
      ]
    }
  ],

  "personality": [
    {
      "id": "pers_ghi789",
      "name": "Outgoing",
      "degree": 4,
      "evidence": [
        {"text": "Loves hanging out with classmates", "timestamp": "2026-03-10T08:00:00.000Z"}
      ]
    }
  ],

  "social_context": {
    "family": {
      "father": {"name": "Zhang Ming", "info": ["Engineer"]},
      "mother": {"name": "Li Hua", "info": ["Teacher"]},
      "brother": [{"name": "Xiao Di", "info": ["5 years old"]}]
    },
    "friends": [
      {"name": "Xiao Ming", "info": ["classmate"]}
    ],
    "others": [
      {"name": null, "relation": "math teacher", "info": ["teaches math", "strict"]}
    ]
  },

  "learning_preferences": {
    "preferred_time": "evening",
    "preferred_style": "visual",
    "difficulty_level": "intermediate"
  }
}
```

Indexes:

| Field            | Type   |
|------------------|--------|
| `user_id`        | unique |
| `interests.id`   | normal |
| `skills.id`      | normal |
| `personality.id` | normal |

---

### 5.4 SQLite — Memory History

File path: configured via `HISTORY_DB_PATH`, defaults to `/app/history/history.db`

```sql
CREATE TABLE history (
    id          TEXT PRIMARY KEY,  -- UUID
    memory_id   TEXT,              -- associated memory UUID
    old_memory  TEXT,              -- content before change (null on ADD)
    new_memory  TEXT,              -- content after change (null on DELETE)
    event       TEXT,              -- ADD | UPDATE | DELETE
    created_at  DATETIME,
    updated_at  DATETIME,
    is_deleted  INTEGER,           -- 0 / 1
    actor_id    TEXT,              -- optional
    role        TEXT               -- optional
);
```

---

## 6. AI Service Dependencies

### 6.1 Current Implementation

The service currently calls AI capabilities directly via external APIs:

#### Embedding

| Item        | Detail                                                        |
|-------------|---------------------------------------------------------------|
| Provider    | Alibaba Cloud DashScope (Qwen)                                |
| Model       | `text-embedding-v4`                                           |
| Dimensions  | 1536                                                          |
| Endpoint    | `https://dashscope.aliyuncs.com/compatible-mode/v1`           |
| Used for    | Generating vectors on memory write; vectorizing queries on search |

#### LLM

| Item           | Detail                                                       |
|----------------|--------------------------------------------------------------|
| Provider       | DeepSeek (official) / VolcEngine (preferred when configured) |
| Model          | `deepseek-chat` / VolcEngine Endpoint ID                     |
| Parameters     | temperature=0.2, max_tokens=2000                             |
| Used for (memory)  | Fact extraction from conversation; ADD/UPDATE/DELETE decisions |
| Used for (profile) | Profile extraction from conversation; field-level ADD/UPDATE/DELETE decisions |

**LLM call chain — `POST /memories`**:

```
Caller → POST /memories
  → LLM: extract facts from conversation
  → Embedding: vector search over existing memories (find related)
  → LLM: decide ADD / UPDATE / DELETE for each fact
  → Write to PostgreSQL (vectors) + SQLite (history)
```

**LLM call chain — `POST /profile`**:

```
Caller → POST /profile
  → LLM: extract profile fields from conversation  (Stage 1)
  → Query existing profile  (PostgreSQL + MongoDB)
  → LLM: decide ADD / UPDATE / DELETE per field    (Stage 2)
  → Write to PostgreSQL (basic_info) + MongoDB (additional_profile)
```

### 6.2 Future Plan

The internal **AI Service** will eventually provide unified Embedding and LLM capabilities. This service will be updated to call the AI Service instead of external APIs. The interface spec will be agreed upon once the AI Service is ready.

Planned changes at migration:

- Vector generation and LLM inference in `POST /memories` → delegate to AI Service
- Two-stage LLM calls in `POST /profile` → delegate to AI Service
- Query vectorization in `POST /search` → delegate to AI Service

**DB Service migration**: Similarly, direct PostgreSQL / MongoDB access may be delegated to an internal DB Service in the future.

---

## 7. Error Handling

### HTTP Status Codes

| Status | Meaning                                                          |
|--------|------------------------------------------------------------------|
| 200    | Success                                                          |
| 400    | Bad request — missing required ID, invalid `source` value, etc. |
| 422    | Validation error — request body failed Pydantic schema check    |
| 500    | Internal error — DB connection failure, LLM error, etc.         |
| 501    | Not implemented — `/vocab` endpoints                            |

### 400 / 422 Response Format

```json
{
  "detail": "At least one identifier (user_id, agent_id, run_id) is required."
}
```

Or (422):

```json
{
  "detail": [
    {
      "loc": ["body", "user_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Response Format

```json
{
  "detail": "specific error message (e.g. DB connection timeout, LLM returned invalid JSON)"
}
```

---

## 8. Constraints & Notes

1. **`user_id` is provided by upstream**: This service does not validate user identity. The caller is responsible for ensuring `user_id` is valid and authorized.

2. **`POST /memories` is LLM-heavy**: Each call triggers LLM inference, typically taking 1–5 seconds. Not recommended for high-frequency synchronous call paths.

3. **`POST /profile` is even slower**: Requires two LLM calls, typically 3–10 seconds. Recommend calling asynchronously or in a background job.

4. **`basic_info` is non-authoritative**: Basic info extracted from conversations (name, birthday, etc.) is for AI personalization reference only, not the source of truth for user records. For authoritative data, query the Master Service / DB Service.

5. **`evidence_limit` parameter**: Defaults to returning the 5 most recent evidence items. Pass `evidence_limit=0` to strip all evidence and reduce response payload size.

6. **Memory scope isolation**: `user_id`, `agent_id`, and `run_id` can be combined. All queries filter strictly by the provided scope(s); memories from different scopes do not bleed across.

7. **`/reset` endpoint**: Wipes all memories for all users. For testing environments only — **do not call in production**.

8. **No authentication**: All endpoints are currently unauthenticated. Callers must ensure access is restricted to the internal network. Auth will be added in a later iteration.
