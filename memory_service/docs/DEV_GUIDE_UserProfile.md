# UserProfile Feature Development Guide

> This document is the complete development guide for the UserProfile module and can directly drive implementation work.

**Version**: 1.0
**Created**: 2025-10-04
**Stage**: MVP (Minimum Viable Product)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Design](#2-architecture-design)
3. [Data Model](#3-data-model)
4. [Core Pipeline](#4-core-pipeline)
5. [Prompt Design](#5-prompt-design)
6. [API Design](#6-api-design)
7. [Error Handling](#7-error-handling)
8. [Implementation Steps](#8-implementation-steps)
9. [Test Cases](#9-test-cases)
10. [Deployment Configuration](#10-deployment-configuration)

---

## 1. Project Overview

### 1.1 Feature Description

Develop a **user profile system** that automatically extracts and manages the following from conversations:
- **Basic info** (name, birthday, location, etc.) → **Non-authoritative data, for reference only**
- **Interests** → Core value
- **Skills** → Core value
- **Personality traits** → Core value
- **Social relationships** → Core value
- **Learning preferences** → Core value

Provides rich user context for AI conversations.

**Important architectural notes**:
- `basic_info`: Basic information extracted from conversations. **Non-authoritative data**, used only for reference, comparison, and personalization.
- `additional_profile`: Deep characteristics such as interests, skills, and personality. **This is the core value.**
- The main service maintains authoritative user basic info. See `discuss/19-manual_data_decision.md`.

### 1.2 Core Design Philosophy

**Evidence-Based**:
- Every judgment is backed by evidence.
- Evidence contains a text description and a timestamp.
- The LLM can synthesize evidence to make intelligent decisions.

### 1.3 Features Not Yet Implemented

- **Vocabulary management** (vocab): Archived to `archived/vocab_design.md`.
- Reason: Logic requires further product discussion.
- Handling: Interface reserved; returns 501 Not Implemented.

---

## 2. Architecture Design

### 2.1 Module Structure

```
mem0/
├── memory/                 # Existing: memory module
│   └── ...
├── user_profile/           # New: user profile module
│   ├── __init__.py         # Exposes UserProfile class
│   ├── main.py             # UserProfile main class
│   ├── profile_manager.py  # Profile business logic
│   ├── vocab_manager.py    # Vocab business logic (reserved, returns Not Implemented)
│   ├── prompts.py          # Prompt templates
│   ├── models.py           # Pydantic data models
│   ├── database/
│   │   ├── __init__.py
│   │   ├── postgres.py     # PostgreSQL operations wrapper
│   │   └── mongodb.py      # MongoDB operations wrapper
│   └── utils.py            # Utility functions
├── llms/                   # Existing: LLM providers
├── embeddings/             # Existing: Embedding providers
└── ...

server/
├── main.py                 # FastAPI service (modified)
└── ...
```

### 2.2 Component Relationships

```
┌─────────────────────────────────────────────────┐
│            FastAPI Server (server/main.py)      │
│  - USER_PROFILE_INSTANCE = UserProfile(config)  │
│  - POST /profile → set_profile()                │
│  - GET /profile → get_profile()                 │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│      UserProfile (mem0/user_profile/main.py)    │
│  - __init__(config)                             │
│  - set_profile(user_id, messages, ...)          │
│  - get_profile(user_id, type, field, ...)       │
└─────────┬───────────────────────────────────────┘
          │
          ├──────────────────┬──────────────────┐
          ▼                  ▼                  ▼
┌──────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  ProfileManager  │ │ PostgresManager │ │ MongoDBManager  │
│  (Business Logic)│ │ (Data Access)   │ │ (Data Access)   │
└──────────────────┘ └─────────────────┘ └─────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────┐
│             LLM (reuses mem0's LLM)              │
│  - DeepSeek (provider: deepseek)                 │
└──────────────────────────────────────────────────┘
```

### 2.3 Data Flow

```
1. User conversation (messages)
   ↓
2. FastAPI receives POST /profile
   ↓
3. UserProfile.set_profile()
   ↓
4. ProfileManager.set_profile()
   ├─ Stage 1: LLM extracts info + evidence
   ├─ Query existing data (PostgreSQL + MongoDB)
   ├─ Stage 2: LLM decides update operations (ADD/UPDATE/DELETE)
   └─ Execute database operations
   ↓
5. Return result to FastAPI
   ↓
6. Return JSON response to client
```

---

## 3. Data Model

### 3.1 PostgreSQL: user_profile Table

**Purpose**: Stores basic information extracted from conversations (**non-authoritative data, for reference only**)

**Important notes**:
- This table stores basic info extracted from conversations by the LLM.
- **Not an authoritative data source.** Used only for reference, comparison, and detecting information changes.
- The main service maintains authoritative user basic information.
- See architecture decision document: `discuss/19-manual_data_decision.md`

```sql
CREATE SCHEMA IF NOT EXISTS user_profile;

CREATE TABLE user_profile.user_profile (
    user_id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Basic info (extracted from conversation, non-authoritative)
    name VARCHAR(100),
    nickname VARCHAR(100),
    english_name VARCHAR(100),
    birthday DATE,
    gender VARCHAR(10),

    -- Geographic and cultural
    nationality VARCHAR(50),
    hometown VARCHAR(100),
    current_city VARCHAR(100),
    timezone VARCHAR(50),
    language VARCHAR(50),

    -- Professional and educational info (for adult users, ages 14-40)
    occupation VARCHAR(100),
    company VARCHAR(200),
    education_level VARCHAR(50),
    university VARCHAR(200),
    major VARCHAR(100),

    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profile_updated_at
    BEFORE UPDATE ON user_profile.user_profile
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Field descriptions**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| user_id | VARCHAR(50) | Unique user identifier | "u123" |
| name | VARCHAR(100) | Full name | "Alice" |
| nickname | VARCHAR(100) | Nickname | "Ali" |
| english_name | VARCHAR(100) | English name | "Alice" |
| birthday | DATE | Date of birth | "1995-07-15" |
| gender | VARCHAR(10) | Gender | "F" / "M" / "Other" |
| nationality | VARCHAR(50) | Nationality | "US" |
| hometown | VARCHAR(100) | Hometown | "Chicago" |
| current_city | VARCHAR(100) | Current city | "New York" |
| timezone | VARCHAR(50) | Timezone | "America/New_York" |
| language | VARCHAR(50) | Primary language | "English" |
| occupation | VARCHAR(100) | Occupation (adult users) | "Software Engineer" |
| company | VARCHAR(200) | Employer (adult users) | "Acme Corp" |
| education_level | VARCHAR(50) | Education level (adult users) | "Bachelor's" / "Master's" |
| university | VARCHAR(200) | University attended (adult users) | "MIT" |
| major | VARCHAR(100) | Field of study (adult users) | "Computer Science" |

---

### 3.2 MongoDB: user_additional_profile Collection

**Purpose**: Stores extended user information (flexible, extensible)

```javascript
{
    "_id": ObjectId("..."),
    "user_id": "u123",

    // interests (overlap with skills is allowed)
    "interests": [
        {
            "id": "0",
            "name": "football",
            "degree": 4,  // 1-5: level of interest
            "evidence": [
                {
                    "text": "Had a great time playing football with friends",
                    "timestamp": "2025-10-01T10:30:00"
                },
                {
                    "text": "Won another match over the weekend",
                    "timestamp": "2025-10-08T15:20:00"
                }
            ]
        }
    ],

    // skills (overlap with interests is allowed)
    "skills": [
        {
            "id": "0",
            "name": "python",
            "degree": 2,  // 1-5: proficiency level
            "evidence": [
                {
                    "text": "Learned Python for loops",
                    "timestamp": "2025-09-20T14:00:00"
                }
            ]
        }
    ],

    // personality
    "personality": [
        {
            "id": "0",
            "name": "curious",
            "degree": 4,  // 1-5: prominence of the trait
            "evidence": [
                {
                    "text": "Proactively asked many questions",
                    "timestamp": "2025-10-01T10:00:00"
                }
            ]
        }
    ],

    // social relationships (uses deep-merge strategy, preserving all existing relations)
    "social_context": {
        // family: immediate relatives ONLY (single object or array)
        "family": {
            // Core relations (single object)
            "spouse": {
                "name": "Jane",  // Specific name; null if not mentioned (❌ do NOT fill with "spouse")
                "info": ["designer", "married 3 years"]
            },
            "father": {
                "name": "John",
                "info": ["doctor", "kind and loving", "plays football"]
            },
            "mother": {
                "name": null,  // Name not mentioned
                "info": ["teacher", "strict", "cooks delicious meals"]
            },

            // Common relations (arrays, multiple allowed)
            "brother": [
                {
                    "name": "Tom",
                    "info": ["older brother", "engineer", "lives in Chicago"]
                }
            ],
            "sister": [
                {
                    "name": null,
                    "info": ["younger sister", "student"]
                }
            ],

            // Grandparents (single objects)
            "grandfather_paternal": {
                "name": null,
                "info": ["retired", "lives in hometown"]
            },

            // Children (arrays, multiple allowed)
            "son": [
                {
                    "name": "Max",
                    "info": ["five years old", "loves drawing"]
                }
            ],
            "daughter": [
                {
                    "name": null,
                    "info": ["two years old", "very active"]
                }
            ]

            // Allowed family relations (see mem0/user_profile/user_profile_schema.py):
            // - Core: spouse, father, mother, son, daughter
            // - Common: brother, sister, grandfather_paternal, grandmother_paternal,
            //           grandfather_maternal, grandmother_maternal
            // - Extended: grandson, granddaughter, father_in_law, mother_in_law
            //
            // ❗ Collateral relatives (uncle/aunt/cousin) go into "others", NOT family
        },

        // friends: friend relationships (array)
        "friends": [
            {
                "name": "Amy",
                "info": ["colleague", "plays football"]
            },
            {
                "name": null,  // Name not mentioned
                "info": ["close friend", "likes movies"]
            }
        ],

        // others: other social relationships (collateral relatives, colleagues, teachers, neighbors, etc.)
        "others": [
            {
                "name": null,
                "relation": "uncle",
                "info": ["engineer", "very kind"]
            },
            {
                "name": "Dr. Smith",
                "relation": "mentor",
                "info": ["teaches machine learning", "very patient"]
            },
            {
                "name": null,
                "relation": "colleague",
                "info": ["frontend engineer", "helpful"]
            }
        ]
    },

    // learning preferences
    "learning_preferences": {
        "preferred_time": "evening",       // "morning" / "afternoon" / "evening"
        "preferred_style": "visual",       // "visual" / "auditory" / "kinesthetic"
        "difficulty_level": "intermediate" // "beginner" / "intermediate" / "advanced"
    },

    // system metadata
    "system_metadata": {
        "created_at": "2025-10-01T00:00:00",
        "updated_at": "2025-10-03T12:30:00",
        "version": 1
    }
}
```

**MongoDB Indexes**:
```javascript
db.user_additional_profile.createIndex({ "user_id": 1 }, { unique: true });
db.user_additional_profile.createIndex({ "interests.name": 1 });
db.user_additional_profile.createIndex({ "skills.name": 1 });
db.user_additional_profile.createIndex({ "personality.name": 1 });
```

**Unified field structure** (interests / skills / personality):

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier (UUID) |
| name | string | Item name |
| degree | int (1-5) | Level (interests=preference, skills=proficiency, personality=prominence) |
| evidence | array | List of evidence entries |
| evidence[].text | string | Evidence description (brief, 1-2 sentences) |
| evidence[].timestamp | ISO8601 | Timestamp |

**social_context field descriptions**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| **family** | object | Immediate relatives ONLY | - |
| family.spouse | object | Spouse (single) | `{"name": "Jane", "info": ["designer"]}` |
| family.father | object | Father (single) | `{"name": "John", "info": ["engineer"]}` |
| family.mother | object | Mother (single) | `{"name": null, "info": ["teacher"]}` |
| family.son | array | Son(s) (multiple allowed) | `[{"name": "Max", "info": ["five years old"]}]` |
| family.daughter | array | Daughter(s) (multiple allowed) | - |
| family.brother | array | Brother(s) (multiple allowed) | `[{"name": "Tom", "info": ["older"]}]` |
| family.sister | array | Sister(s) (multiple allowed) | `[{"name": null, "info": ["younger"]}]` |
| family.grandfather_* | object | Grandfather (paternal/maternal) | - |
| family.grandmother_* | object | Grandmother (paternal/maternal) | - |
| **friends** | array | Friends list | - |
| friends[].name | string\|null | Name (null if not mentioned) | "Amy" or null |
| friends[].info | array<string> | Related information | `["colleague", "kind"]` |
| **others** | array | Other social relationships (collateral relatives, colleagues, etc.) | - |
| others[].name | string\|null | Name (null if not mentioned) | "Dr. Smith" or null |
| others[].relation | string | Relationship type (**required**) | "uncle", "mentor", "colleague" |
| others[].info | array<string> | Related information | `["engineer", "kind"]` |

**Important design notes**:

1. **name field rules**:
   - ✅ Only fill with a specific name (e.g., "Jane", "John")
   - ✅ Set to `null` if not mentioned
   - ❌ **Do NOT** fill with a relationship label (e.g., "wife", "father")

2. **family relation categories** (based on current user persona: adult):
   - **Core**: spouse, father, mother, son, daughter
   - **Common**: brother, sister, grandfather_paternal, grandmother_paternal, grandfather_maternal, grandmother_maternal
   - **Extended**: grandson, granddaughter, father_in_law, mother_in_law

3. **Handling collateral relatives**:
   - ❌ **Do NOT** place in family (e.g., uncle/aunt/cousin)
   - ✅ Place in **others**, using the `relation` field to distinguish (e.g., "uncle" vs "aunt" vs "cousin")

4. **Deep-merge strategy** (CRITICAL):
   - `social_context` uses **deep merge**, not replacement.
   - When adding a new relation (e.g., son), **preserve** existing relations (e.g., spouse/father/mother).
   - See `mem0/user_profile/profile_manager.py::_deep_merge_social_context()`

5. **Unified field format**:
   - family members: `{"name": str|null, "info": [str]}`
   - friends members: `{"name": str|null, "info": [str]}`
   - others members: `{"name": str|null, "relation": str, "info": [str]}`

6. **❗Personality conflict detection mechanism** (CRITICAL - added 2025-10-05):

   **Background**: The LLM may fail to detect semantic conflicts, leading to contradictory traits coexisting (e.g., "conscientious" degree=4 + "careless" degree=4).

   **Solution**: Add Rule 9 — conflict detection and degree validity validation — to UPDATE_PROFILE_PROMPT.

   **Conflict detection rules**:

   a. **Insufficient evidence for conflict → SKIP**
      - Example: Existing "conscientious" (degree 4, 4 evidence), new single instance of "careless".
      - Decision: SKIP — a single event is insufficient to override strong evidence.

   b. **Moderate conflict → UPDATE (lower degree)**
      - Example: Existing "conscientious" (degree 5), 3 new "careless" evidence entries.
      - Decision: UPDATE "conscientious" degree → 3.

   c. **Genuine change → DELETE old + ADD new**
      - Example: Existing "introverted" (old evidence, 1 year ago), 6 new "extroverted" evidence entries (past 3 months).
      - Decision: DELETE "introverted", ADD "extroverted".

   d. **Complex personality — coexisting contradictions** (RARE, strict conditions):
      - ✅ Allowed: Both sides have 5+ evidence with clear contextual separation (e.g., work vs. home).
      - ❌ Not allowed: Insufficient evidence or no contextual separation.
      - Example: work context "introverted" (5 evidence) + family context "extroverted" (5 evidence) = valid coexistence.

   **Degree validity rules**:
   - degree 1-2: 1-2 evidence entries sufficient
   - degree 3: requires 3-5 evidence entries
   - degree 4: requires 5-8 evidence entries
   - degree 5: requires 8+ evidence entries
   - ❌ A single event should not produce degree 4-5.

   **Implementation locations**:
   - Prompt: `mem0/user_profile/prompts.py` — UPDATE_PROFILE_PROMPT Rule 9
   - Tests: `test/test_personality_conflict.py` — 4 scenario tests
   - See: `discuss/34-personality_conflict_implemented.md`

**User persona adjustment guide**:

If the user persona needs to be adjusted in the future, modify the following files:

1. `mem0/user_profile/user_profile_schema.py` — `FAMILY_RELATIONS` definition
2. `mem0/user_profile/prompts.py` — allowed relations list and examples in the extraction prompt
3. `DEV_GUIDE_UserProfile.md` — this document's family relation category section

---

## 4. Core Pipeline

### 4.1 set_profile Full Flow

```
┌─────────────────────────────────────────────────┐
│  Input: user_id, messages, manual_data, options │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Step 1: Merge frontend data and LLM extraction │
│  (basic_info)                                   │
│  - If manual_data is provided, use it first     │
│  - Otherwise, call LLM to extract basic_info    │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Step 2: LLM extracts extended info (Stage 1)   │
│  - Extracts interests, skills, personality      │
│  - Each item includes name and evidence         │
│  - Returns JSON format                          │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Step 3: Query existing data                    │
│  - PostgreSQL: user_profile (basic_info)        │
│  - MongoDB: user_additional_profile (all)       │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Step 4: Direct UPSERT for basic_info           │
│  - No LLM judgment required                     │
│  - Update if value present, keep if not         │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Step 5: LLM decides extended info updates      │
│  (Stage 2)                                      │
│  - Input: existing data + newly extracted data  │
│  - Output: ADD / UPDATE / DELETE decisions      │
│  - Includes new degree and evidence             │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Step 6: Execute database operations            │
│  - Per-field fault tolerance                    │
│  - Log operations                               │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Output: Return update results                  │
│  - basic_info: which fields were updated        │
│  - interests/skills/personality: operations     │
└─────────────────────────────────────────────────┘
```

### 4.2 get_profile Query Flow

```
┌─────────────────────────────────────────────────┐
│  Input: user_id, type, field, query_all         │
└─────────────────┬───────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
    type="basic"      type="additional"
         │                 │
         ▼                 ▼
  Query PostgreSQL    Query MongoDB
         │                 │
         │                 ├─ field="" → return all
         │                 ├─ field="interests" → return interests
         │                 └─ field="social_context.father.name" → dot-notation query
         │                 │
         └────────┬────────┘
                  ▼
         Merge results (if type="all")
                  │
                  ▼
         Return JSON response
```

---

## 5. Prompt Design

### 5.1 Stage 1: Extract Information and Evidence

**Prompt template** (`mem0/user_profile/prompts.py`):

```python
PROFILE_EXTRACTION_PROMPT = """You are a user profile expert skilled at extracting user characteristics from conversations.

**Task**: Extract the user's interests, skills, and personality traits from the conversation, and record supporting evidence.

**Conversation**:
{messages}

**Return JSON format** (strictly follow this format):
{{
    "basic_info": {{
        "current_city": "New York",
        "hometown": "Chicago"
    }},
    "interests": [
        {{
            "name": "football",
            "evidence": "Had a great time playing football with friends"
        }}
    ],
    "skills": [
        {{
            "name": "python",
            "evidence": "Learned Python for loops"
        }}
    ],
    "personality": [
        {{
            "name": "curious",
            "evidence": "Proactively asked many questions"
        }}
    ]
}}

**Extraction rules**:
1. **basic_info**: Only extract fields explicitly mentioned in the conversation.
   - Available fields: current_city, hometown, nationality, timezone, language
   - If not mentioned, return empty object {{}}

2. **interests**: Activities or things the user likes or is interested in.
   - name: Name of the interest (in English)
   - evidence: Concrete factual description (1-2 sentences, extracted from the conversation)

3. **skills**: Skills or abilities the user has or can perform.
   - name: Name of the skill (in English)
   - evidence: Concrete factual description

4. **personality**: Personality traits inferred from the conversation.
   - name: Personality trait (in English, e.g., "curious", "extroverted", "patient")
   - evidence: Behavioral description supporting this trait

**Notes**:
- Only extract content that is explicitly mentioned or clearly demonstrated in the conversation.
- Do not over-infer.
- Evidence must be specific facts, not vague summaries.
- If a category has no information, return an empty list [].
- Strictly return JSON format without any additional text.
- Keep output in English.
"""

def get_profile_extraction_prompt(messages: List[Dict[str, str]]) -> str:
    """Generate the Stage 1 extraction prompt"""
    # Format messages
    formatted_messages = "\n".join([
        f"{msg['role']}: {msg['content']}"
        for msg in messages
    ])

    return PROFILE_EXTRACTION_PROMPT.format(messages=formatted_messages)
```

---

### 5.2 Stage 2: Decide Update Operations

**Prompt template**:

```python
PROFILE_UPDATE_DECISION_PROMPT = """You are a user profile management expert responsible for deciding how to update a user profile.

**Current user profile**:
{current_profile}

**Information extracted from the latest conversation**:
{extracted_info}

**Task**: Decide how to update the user profile, returning ADD / UPDATE / DELETE decisions.

**Return JSON format** (strictly follow):
{{
    "interests": [
        {{
            "id": "0",
            "name": "football",
            "event": "UPDATE",
            "new_degree": 4,
            "new_evidence": {{
                "text": "Had a great time playing football with friends"
                // Note: timestamp is NOT required; the backend will add it automatically
            }},
            "reason": "Added positive evidence"
        }},
        {{
            "name": "hiking",
            "event": "ADD",
            "new_degree": 3,
            "new_evidence": {{
                "text": "Went hiking over the weekend and loved it"
                // Note: timestamp is NOT required; the backend will add it automatically
            }},
            "reason": "Newly discovered interest"
        }}
    ],
    "skills": [...],
    "personality": [...]
}}

**Important notes**:
- The LLM only needs to return the evidence `text` field.
- The `timestamp` is added automatically by the backend (`profile_manager.py::_add_timestamps_to_evidence()`).
- See `discuss/22-prompts-implemented.md` for details.

**Decision rules**:

1. **ADD (new entry)**:
   - Name does not exist in the current profile.
   - A new ID will be generated by the application (not required in the response).
   - Initial degree: judged based on evidence quality (typically 2-3).

2. **UPDATE (update existing)**:
   - Name already exists.
   - Must use the original ID.
   - Append new evidence.
   - Re-evaluate degree (considering all evidence).

3. **DELETE (remove entry)**:
   - New conversation explicitly states the user no longer likes/has/exhibits the characteristic.
   - Consider:
     * Volume of old evidence: high → delete cautiously
     * Recency of old evidence: recent → may be a temporary mood, lower degree instead
     * Recency of old evidence: old → may be a genuine change, deletion is appropriate

4. **degree evaluation** (1-5):
   - interests: 1=slight interest, 2=moderate, 3=likes, 4=really likes, 5=passion
   - skills: 1=beginner, 2=novice, 3=intermediate, 4=advanced, 5=expert
   - personality: 1=barely noticeable, 2=occasional, 3=moderate, 4=prominent, 5=very prominent
   - Basis: evidence volume + quality + temporal distribution

**Conflict handling examples**:

- Scenario 1: Many old evidence entries (6+) with recent timestamps (within 3 months), user says "I don't like it anymore"
  → Judgment: Likely a temporary mood
  → Action: UPDATE, new_degree = max(1, old_degree - 2)

- Scenario 2: Many old evidence entries but from long ago (1+ year), user says "I don't like it anymore"
  → Judgment: Interest may have genuinely changed
  → Action: DELETE

- Scenario 3: Few old evidence entries (1-2), user says "I don't like it anymore"
  → Judgment: Previous judgment may have been inaccurate
  → Action: DELETE

**Evidence timing analysis** (provided):
{evidence_analysis}

**Current time**: {current_time}

**Notes**:
- IDs must come from the current profile; do not generate new ones.
- degree must be an integer from 1-5.
- The reason field should briefly explain the rationale.
- Strictly return JSON format.
"""

def get_profile_update_decision_prompt(
    current_profile: Dict[str, Any],
    extracted_info: Dict[str, Any],
    evidence_analysis: Optional[Dict[str, Any]] = None
) -> str:
    """Generate the Stage 2 update decision prompt"""
    import json
    from datetime import datetime

    current_time = datetime.now().isoformat()

    # Format current profile (simplified display)
    formatted_current = format_profile_for_prompt(current_profile)

    # Format extracted information
    formatted_extracted = json.dumps(extracted_info, ensure_ascii=False, indent=2)

    # Format evidence analysis (if provided)
    formatted_analysis = ""
    if evidence_analysis:
        formatted_analysis = json.dumps(evidence_analysis, ensure_ascii=False, indent=2)

    return PROFILE_UPDATE_DECISION_PROMPT.format(
        current_profile=formatted_current,
        extracted_info=formatted_extracted,
        evidence_analysis=formatted_analysis,
        current_time=current_time
    )

def format_profile_for_prompt(profile: Dict[str, Any]) -> str:
    """Format profile data for LLM readability"""
    lines = []

    for category in ["interests", "skills", "personality"]:
        items = profile.get(category, [])
        if items:
            lines.append(f"\n{category}:")
            for item in items:
                evidence_summary = f"{len(item.get('evidence', []))} evidence entries"
                lines.append(f"  - {item['name']} (degree={item['degree']}, {evidence_summary})")
                # Optionally show the most recent 2 evidence entries
                for ev in item.get('evidence', [])[:2]:
                    lines.append(f"    * \"{ev['text']}\" ({ev['timestamp'][:10]})")

    return "\n".join(lines)
```

---

## 6. API Design

### 6.1 POST /profile (Update User Profile)

**Request**:

```http
POST /profile HTTP/1.1
Content-Type: application/json

{
    "user_id": "u123",
    "messages": [
        {
            "role": "user",
            "content": "I moved yesterday, my new place is in New York"
        },
        {
            "role": "assistant",
            "content": "Congratulations on the new place!"
        },
        {
            "role": "user",
            "content": "Yes, and the food scene here is amazing"
        }
    ],
    "manual_data": {
        "name": "Alice",
        "birthday": "1995-07-15"
    },
    "options": {
        "update_basic": true,
        "update_interests": true,
        "update_skills": true,
        "update_personality": true,
        "query_all": true
    }
}
```

**Parameter descriptions**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | Yes | User ID |
| messages | array | Yes | List of conversation messages |
| messages[].role | string | Yes | "user" / "assistant" |
| messages[].content | string | Yes | Message content |
| manual_data | object | No | Data manually entered by the frontend (highest priority) |
| options | object | No | Control options |
| options.update_basic | bool | No | Whether to update basic info (default true) |
| options.update_interests | bool | No | Whether to update interests (default true) |
| options.update_skills | bool | No | Whether to update skills (default true) |
| options.update_personality | bool | No | Whether to update personality (default true) |
| options.query_all | bool | No | Whether to query all data (default true; false requires specifying fields) |

**Response**:

```json
{
    "results": {
        "basic_info": {
            "updated_fields": ["current_city"],
            "values": {
                "current_city": "New York",
                "name": "Alice",
                "birthday": "1995-07-15"
            }
        },
        "interests": [
            {
                "name": "dining out",
                "event": "ADD",
                "degree": 3
            }
        ],
        "skills": [],
        "personality": []
    }
}
```

---

### 6.2 GET /profile (Get User Profile)

**Request examples**:

```http
# Get all (evidence defaults to latest 5 entries)
GET /profile?user_id=u123

# Filter additional_profile fields
GET /profile?user_id=u123&fields=interests,skills

# Limit evidence count (-1 means all)
GET /profile?user_id=u123&evidence_limit=10
GET /profile?user_id=u123&evidence_limit=-1  # return all evidence
```

**Parameter descriptions**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | Yes | User ID |
| fields | string | No | Comma-separated field names, e.g. "interests,skills"; only returns specified fields |
| evidence_limit | int | No | Number of evidence entries per item, default 5, -1 for all |

**Response examples**:

```json
// type=all
{
    "user_id": "u123",
    "basic_info": {
        "name": "Alice",
        "birthday": "1995-07-15",
        "current_city": "New York",
        ...
    },
    "additional_profile": {
        "interests": [...],
        "skills": [...],
        "personality": [...],
        ...
    }
}

// type=additional&field=interests
{
    "user_id": "u123",
    "interests": [
        {
            "id": "0",
            "name": "football",
            "degree": 4,
            "evidence": [...]
        }
    ]
}

// type=additional&field=social_context.father.name
{
    "user_id": "u123",
    "field": "social_context.father.name",
    "value": "John"
}
```

---

### 6.3 GET /profile/missing-fields (Get Missing Fields)

**Purpose**: Query which fields are missing from the user profile, so the main service can proactively ask for that information in subsequent conversations.

**Request examples**:

```http
# Query all missing fields
GET /profile/missing-fields?user_id=u123

# Query only PostgreSQL basic_info missing fields
GET /profile/missing-fields?user_id=u123&source=pg

# Query only MongoDB additional_profile missing fields
GET /profile/missing-fields?user_id=u123&source=mongo
```

**Parameter descriptions**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | Yes | User ID |
| source | string | No | "pg" / "mongo" / "both" (default "both") |

**Complete field definitions**:

- **PostgreSQL (basic_info)**: name, nickname, english_name, birthday, gender, nationality, hometown, current_city, timezone, language, occupation, company, education_level, university, major
- **MongoDB (additional_profile)**: interests, skills, personality, social_context, learning_preferences

**Response example**:

```json
{
    "user_id": "u123",
    "missing_fields": {
        "basic_info": ["hometown", "gender", "birthday", "occupation"],
        "additional_profile": ["personality", "learning_preferences"]
    }
}
```

**Use case**:
The main service can use the returned missing fields to add guidance to the system prompt, such as:
```
The following user profile fields are missing: hometown, gender, occupation
Please ask for this information naturally during conversation.
```

---

### 6.4 DELETE /profile (Delete User Profile)

**Request example**:

```http
DELETE /profile?user_id=u123
```

**Parameter descriptions**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | Yes | User ID |

**Response example**:

```json
{
    "success": true,
    "basic_info_deleted": true,
    "additional_profile_deleted": true
}
```

---

### 6.5 Cold Start Integration

**Feature overview**:

When a user first accesses the system, if MainService already has basic profile data for that user (e.g., personality tags, interests), the system will automatically pull and import that data, avoiding redundant input.

**Trigger conditions**:

- The user does not exist in the system (both basic_info and additional_profile are empty).
- The `MAINSERVICE_BASE_URL` environment variable is configured.
- The MainService endpoint returns a successful response.

**Data mapping rules**:

| MainService field | Target location in MyMem0 | Mapping rule |
|------------------|---------------------------|--------------|
| `displayName` | `basic_info.nickname` | Direct copy |
| `gender` | `basic_info.gender` | `1→"male"`, `2→"female"`, other→`"unknown"` |
| `age` | - | **Ignored** (MyMem0 only stores birthday) |
| `personalityTraits` | `additional_profile.personality` | Comma-separated → multiple items, degree=3 |
| `hobbies` | `additional_profile.interests` | Comma-separated → multiple items, degree=3 |

**Configuration**:

1. Environment variable (`.env`):
```bash
# MainService Configuration (for cold start)
MAINSERVICE_BASE_URL=http://localhost:8099/main
```

2. Docker Compose configuration:
```yaml
environment:
  - MAINSERVICE_BASE_URL=${MAINSERVICE_BASE_URL:-http://localhost:8099/main}
```

**Call flow**:

```
User requests GET /profile?user_id=12345
    ↓
1. Query PostgreSQL basic_info → empty
2. Query MongoDB additional_profile → empty
    ↓
3. User not found AND MAINSERVICE_BASE_URL is configured
    ↓
4. Call MainService: GET /user/12345/summary
   (Not yet implemented; returns stub response)
   - Timeout: 1 second (intra-cluster network)
   - On failure: log warning, return empty profile (non-blocking)
    ↓
5. Transform data (gender mapping, comma-separated parsing)
    ↓
6. Store to database:
   - PostgreSQL: nickname, gender
   - MongoDB: personality items, interests items
   - Evidence: "Initial profile from user registration"
    ↓
7. Re-query and return profile
```

**Example**:

**MainService response**:
```json
{
  "success": true,
  "data": {
    "id": 12345,
    "displayName": "Alex",
    "age": 28,
    "gender": 1,
    "personalityTraits": "outgoing,ambitious,creative",
    "hobbies": "basketball,music,reading"
  }
}
```

**MyMem0 stored result**:
```json
{
  "user_id": "12345",
  "basic_info": {
    "nickname": "Alex",
    "gender": "male"
  },
  "additional_profile": {
    "personality": [
      {
        "name": "outgoing",
        "degree": 3,
        "evidence": [
          {
            "text": "Initial profile from user registration",
            "timestamp": "2025-10-21T10:30:45.123456"
          }
        ]
      },
      {"name": "ambitious", "degree": 3, "evidence": [...]},
      {"name": "creative", "degree": 3, "evidence": [...]}
    ],
    "interests": [
      {"name": "basketball", "degree": 3, "evidence": [...]},
      {"name": "music", "degree": 3, "evidence": [...]},
      {"name": "reading", "degree": 3, "evidence": [...]}
    ]
  }
}
```

**Error handling**:

- **MainService timeout/unreachable**: Log warning, return empty profile; user can continue normally.
- **MainService returns error**: Log warning, return empty profile.
- **Malformed data**: Log warning, skip the malformed fields.
- **Concurrent requests**: Database upsert is naturally idempotent; no side effects.

**Architectural note**:

⚠️ **Architecture trade-off**: The design principle of `basic_info` is "conversation-extracted reference data", but the cold-start import brings in authoritative data from MainService. This is an accepted architectural compromise to improve user experience. See `discuss/40-cold_start_implementation.md`.

**Disabling cold start**:

To disable the cold-start feature, set `MAINSERVICE_BASE_URL` to empty or leave it unset:
```bash
MAINSERVICE_BASE_URL=
```

---

### 6.6 POST /vocab and GET /vocab (Reserved)

**Implementation**: Returns 501 Not Implemented

```python
@app.post("/vocab", summary="Update user vocabulary (Not Implemented)")
def set_vocab():
    raise HTTPException(
        status_code=501,
        detail="Vocabulary management feature is not implemented in this version. See archived/vocab_design.md for future plans."
    )

@app.get("/vocab", summary="Get user vocabulary (Not Implemented)")
def get_vocab():
    raise HTTPException(
        status_code=501,
        detail="Vocabulary management feature is not implemented in this version."
    )
```

---

## 7. Error Handling

### 7.1 Four-Layer Fault Tolerance

#### Layer 1: LLM Call Fault Tolerance

```python
def call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> str:
    """LLM call with retry"""
    for attempt in range(max_retries + 1):
        try:
            response = self.llm.generate_response(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return response
        except Exception as e:
            logger.error(f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt == max_retries:
                raise Exception(f"LLM service unavailable after {max_retries + 1} attempts")
            time.sleep(1)  # Wait 1 second before retrying
```

#### Layer 2: JSON Parse Fault Tolerance

```python
from mem0.memory.utils import remove_code_blocks

def parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse LLM-returned JSON with fault tolerance"""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed, attempting to clean: {e}")

        # Try removing markdown code block markers
        cleaned = remove_code_blocks(response)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error(f"JSON parse failed after cleaning. Response: {response}")
            return {}  # Return empty dict rather than crashing
```

#### Layer 3: Per-Field Fault Tolerance

```python
def update_additional_profile(self, user_id: str, decisions: Dict[str, Any]) -> Dict[str, Any]:
    """Update extended profile with per-field fault tolerance"""
    results = {}

    for field in ["interests", "skills", "personality"]:
        try:
            field_decisions = decisions.get(field, [])
            field_results = self._update_field(user_id, field, field_decisions)
            results[field] = field_results
        except Exception as e:
            logger.error(f"Failed to update {field} for user {user_id}: {e}")
            results[field] = {"error": str(e), "updated": []}

    return results
```

#### Layer 4: Database Transactions (PostgreSQL, optional)

```python
def update_basic_info_transactional(self, user_id: str, data: Dict[str, Any]):
    """Update basic info using a transaction"""
    conn = self.pool.getconn()
    try:
        conn.autocommit = False
        cursor = conn.cursor()

        # Execute multiple SQL operations
        cursor.execute(...)
        cursor.execute(...)

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction failed, rolled back: {e}")
        raise
    finally:
        cursor.close()
        self.pool.putconn(conn)
```

---

### 7.2 Error Code Design

| HTTP Status | Scenario | Response Example |
|-------------|----------|-----------------|
| 200 OK | Success | `{"results": {...}}` |
| 400 Bad Request | Invalid parameters | `{"detail": "user_id is required"}` |
| 404 Not Found | User not found | `{"detail": "User u123 not found"}` |
| 500 Internal Server Error | Server error | `{"detail": "LLM service unavailable"}` |
| 501 Not Implemented | Feature not implemented | `{"detail": "Vocabulary feature not implemented"}` |

---

## 8. Implementation Steps

### Phase 1: Foundation (2-3 days)

**Goal**: Set up the basic framework and database connections.

#### 1.1 Create Directory Structure
```bash
mkdir -p mem0/user_profile/database
touch mem0/user_profile/__init__.py
touch mem0/user_profile/main.py
touch mem0/user_profile/profile_manager.py
touch mem0/user_profile/vocab_manager.py
touch mem0/user_profile/prompts.py
touch mem0/user_profile/models.py
touch mem0/user_profile/utils.py
touch mem0/user_profile/database/__init__.py
touch mem0/user_profile/database/postgres.py
touch mem0/user_profile/database/mongodb.py
```

#### 1.2 Implement Database Managers

**postgres.py** (core methods):
```python
import psycopg2
from psycopg2 import pool
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class PostgresManager:
    def __init__(self, config: Dict[str, Any]):
        """Initialize PostgreSQL connection pool"""
        self.pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"]
        )

    def upsert_basic_info(self, user_id: str, data: Dict[str, Any]) -> None:
        """Insert or update basic info"""
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor()

            # Build UPSERT SQL
            fields = list(data.keys())
            placeholders = ["%s"] * len(fields)

            sql = f"""
                INSERT INTO user_profile.user_profile (user_id, {', '.join(fields)})
                VALUES (%s, {', '.join(placeholders)})
                ON CONFLICT (user_id)
                DO UPDATE SET
                    {', '.join([f"{f} = EXCLUDED.{f}" for f in fields])},
                    updated_at = CURRENT_TIMESTAMP
            """

            values = [user_id] + [data[f] for f in fields]
            cursor.execute(sql, values)
            conn.commit()

            logger.info(f"Upserted basic_info for user {user_id}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to upsert basic_info for user {user_id}: {e}")
            raise
        finally:
            cursor.close()
            self.pool.putconn(conn)

    def get_basic_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get basic info"""
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_profile.user_profile WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()

            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
        finally:
            cursor.close()
            self.pool.putconn(conn)
```

**mongodb.py** (core methods):
```python
from pymongo import MongoClient
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class MongoDBManager:
    def __init__(self, config: Dict[str, Any]):
        """Initialize MongoDB connection"""
        self.client = MongoClient(
            config["uri"],
            maxPoolSize=10
        )
        self.db = self.client[config["database"]]
        self.collection = self.db["user_additional_profile"]

    def get_additional_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get extended profile"""
        doc = self.collection.find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)  # Remove MongoDB's _id
        return doc

    def update_field(self, user_id: str, field: str, items: List[Dict[str, Any]]) -> None:
        """Update a specified field (interests / skills / personality)"""
        self.collection.update_one(
            {"user_id": user_id},
            {"$set": {
                field: items,
                "system_metadata.updated_at": datetime.now().isoformat()
            }},
            upsert=True
        )
        logger.info(f"Updated {field} for user {user_id}")

    def add_item_to_field(self, user_id: str, field: str, item: Dict[str, Any]) -> None:
        """Append a new item to a field"""
        self.collection.update_one(
            {"user_id": user_id},
            {"$push": {field: item}},
            upsert=True
        )
```

#### 1.3 Configuration Integration

**server/main.py** (modifications):
```python
# New environment variables
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://mongodb:27017")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "mem0_profile")

# Extend DEFAULT_CONFIG
DEFAULT_CONFIG = {
    # ... existing config ...

    "user_profile": {
        "postgres": {
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "database": POSTGRES_DB,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD,
            "schema": "user_profile"
        },
        "mongodb": {
            "uri": MONGODB_URI,
            "database": MONGODB_DATABASE
        }
    }
}
```

**Acceptance criteria**:
- ✅ Directory structure created
- ✅ PostgreSQL connection successful; UPSERT and query work
- ✅ MongoDB connection successful; read/write works
- ✅ Configuration loads correctly

---

### Phase 2: Profile Features (3-4 days)

**Goal**: Implement the full set_profile and get_profile functionality.

#### 2.1 Implement ProfileManager

**profile_manager.py**:
```python
class ProfileManager:
    def __init__(self, llm, postgres, mongodb):
        self.llm = llm
        self.postgres = postgres
        self.mongodb = mongodb

    def set_profile(
        self,
        user_id: str,
        messages: List[Dict[str, str]],
        manual_data: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """Complete set_profile flow"""
        options = options or {}
        results = {}

        # Step 1: Extract information (Stage 1 LLM)
        extracted = self._extract_profile(messages)

        # Step 2: Update basic_info
        if options.get("update_basic", True):
            basic_info = self._merge_basic_info(
                extracted.get("basic_info", {}),
                manual_data
            )
            if basic_info:
                self.postgres.upsert_basic_info(user_id, basic_info)
                results["basic_info"] = basic_info

        # Step 3: Query existing extended profile
        current_additional = self.mongodb.get_additional_profile(user_id) or {}

        # Step 4: LLM decides updates (Stage 2 LLM)
        decisions = self._decide_profile_updates(current_additional, extracted)

        # Step 5: Execute updates
        if options.get("update_interests", True):
            results["interests"] = self._update_interests(user_id, decisions.get("interests", []))
        # ... skills, personality follow the same pattern ...

        return {"results": results}

    def _extract_profile(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Stage 1: LLM extraction"""
        from mem0.user_profile.prompts import get_profile_extraction_prompt

        prompt = get_profile_extraction_prompt(messages)
        response = self.llm.generate_response(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        return parse_llm_response(response)

    def _decide_profile_updates(
        self,
        current: Dict[str, Any],
        extracted: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Stage 2: LLM decision"""
        from mem0.user_profile.prompts import get_profile_update_decision_prompt

        prompt = get_profile_update_decision_prompt(current, extracted)
        response = self.llm.generate_response(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        return parse_llm_response(response)
```

#### 2.2 Implement UserProfile Main Class

**main.py**:
```python
from mem0.configs.base import MemoryConfig
from mem0.utils.factory import LlmFactory
from mem0.user_profile.database.postgres import PostgresManager
from mem0.user_profile.database.mongodb import MongoDBManager
from mem0.user_profile.profile_manager import ProfileManager

class UserProfile:
    def __init__(self, config: MemoryConfig):
        self.config = config

        # Reuse LLM
        self.llm = LlmFactory.create(
            config.llm.provider,
            config.llm.config
        )

        # Initialize databases
        self.postgres = PostgresManager(config.user_profile["postgres"])
        self.mongodb = MongoDBManager(config.user_profile["mongodb"])

        # Initialize business logic
        self.profile_manager = ProfileManager(
            llm=self.llm,
            postgres=self.postgres,
            mongodb=self.mongodb
        )

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]):
        """Create instance from dict config"""
        from mem0.configs.base import MemoryConfig
        config = MemoryConfig(**config_dict)
        return cls(config)

    def set_profile(self, user_id: str, messages: List[Dict[str, str]], **kwargs):
        """Public interface"""
        return self.profile_manager.set_profile(user_id, messages, **kwargs)

    def get_profile(self, user_id: str, type: str = "all", field: Optional[str] = None):
        """Public interface"""
        return self.profile_manager.get_profile(user_id, type, field)
```

#### 2.3 Integrate with FastAPI

**server/main.py** (modifications):
```python
from mem0.user_profile import UserProfile

# Create instance
USER_PROFILE_INSTANCE = UserProfile.from_config(DEFAULT_CONFIG)

# New routes
@app.post("/profile", summary="Update user profile")
def set_profile(
    user_id: str,
    messages: List[Message],
    manual_data: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, bool]] = None
):
    try:
        result = USER_PROFILE_INSTANCE.set_profile(
            user_id=user_id,
            messages=[m.model_dump() for m in messages],
            manual_data=manual_data,
            options=options
        )
        return JSONResponse(content=result)
    except Exception as e:
        logging.exception("Error in set_profile:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile", summary="Get user profile")
def get_profile(
    user_id: str,
    type: str = "all",
    field: Optional[str] = None
):
    try:
        result = USER_PROFILE_INSTANCE.get_profile(
            user_id=user_id,
            type=type,
            field=field
        )
        return JSONResponse(content=result)
    except Exception as e:
        logging.exception("Error in get_profile:")
        raise HTTPException(status_code=500, detail=str(e))
```

**Acceptance criteria**:
- ✅ POST /profile can be called successfully to update
- ✅ GET /profile can be called successfully to query
- ✅ LLM correctly extracts information
- ✅ LLM correctly decides updates
- ✅ Data correctly stored in PostgreSQL and MongoDB

---

### Phase 3: Testing and Optimization (1-2 days)

See Section 9 for test cases.

---

### Phase 4: Documentation and Deployment (1 day)

- Update CLAUDE.md
- Update TODO.md
- Create database initialization scripts
- Update docker-compose.yaml
- Update .env.example

---

## 9. Test Cases

### 9.1 Basic Functionality Tests

```python
# test/test_user_profile.py

def test_set_profile_basic():
    """Test basic info update"""
    response = client.post("/profile", json={
        "user_id": "test_user_1",
        "messages": [
            {"role": "user", "content": "My name is Alice, I'm 28 years old and I live in New York"}
        ]
    })

    assert response.status_code == 200
    data = response.json()

    assert "basic_info" in data["results"]
    assert data["results"]["basic_info"]["values"]["name"] == "Alice"
    assert data["results"]["basic_info"]["values"]["current_city"] == "New York"

def test_set_profile_interests():
    """Test interests update"""
    response = client.post("/profile", json={
        "user_id": "test_user_2",
        "messages": [
            {"role": "user", "content": "I love playing football, I play with friends every week"}
        ]
    })

    assert response.status_code == 200
    data = response.json()

    assert "interests" in data["results"]
    assert len(data["results"]["interests"]) > 0
    assert any(item["name"] == "football" for item in data["results"]["interests"])

def test_get_profile():
    """Test getting profile"""
    # Set first
    client.post("/profile", json={
        "user_id": "test_user_3",
        "messages": [{"role": "user", "content": "I enjoy programming"}]
    })

    # Then get
    response = client.get("/profile?user_id=test_user_3&type=all")
    assert response.status_code == 200

    data = response.json()
    assert "basic_info" in data or "additional_profile" in data
```

### 9.2 Edge Case Tests

```python
def test_empty_messages():
    """Test empty messages"""
    response = client.post("/profile", json={
        "user_id": "test_user_4",
        "messages": []
    })
    # Should handle gracefully and return empty results
    assert response.status_code == 200

def test_invalid_json_from_llm():
    """Test invalid JSON from LLM (requires mock)"""
    # Use a mock to make the LLM return invalid JSON
    # Should be caught by Layer 2 fault tolerance, returning empty results rather than crashing
    pass

def test_conflict_resolution():
    """Test conflict handling"""
    # First establish an interest
    client.post("/profile", json={
        "user_id": "test_user_5",
        "messages": [{"role": "user", "content": "I love football"}] * 5
    })

    # Then express dislike
    response = client.post("/profile", json={
        "user_id": "test_user_5",
        "messages": [{"role": "user", "content": "I don't like football anymore"}]
    })

    # Check whether degree was lowered or entry was deleted
    # (exact behavior depends on LLM judgment)
```

---

## 10. Deployment Configuration

### 10.1 Database Initialization Scripts

**scripts/init_user_profile_postgres.sql**:
```sql
-- Create schema
CREATE SCHEMA IF NOT EXISTS user_profile;

-- Create table
CREATE TABLE IF NOT EXISTS user_profile.user_profile (
    -- ... see Section 3.1 ...
);

-- Create trigger
-- ... see Section 3.1 ...
```

**scripts/init_user_profile_mongodb.js**:
```javascript
// Connect to database
db = db.getSiblingDB('mem0_profile');

// Create collection (if not exists)
db.createCollection('user_additional_profile');

// Create indexes
db.user_additional_profile.createIndex({ "user_id": 1 }, { unique: true });
db.user_additional_profile.createIndex({ "interests.name": 1 });
db.user_additional_profile.createIndex({ "skills.name": 1 });
db.user_additional_profile.createIndex({ "personality.name": 1 });

print("MongoDB initialization completed");
```

### 10.2 docker-compose.yaml Updates

```yaml
version: '3.8'

services:
  postgres:
    # ... existing config ...

  mongodb:  # new
    image: mongo:7.0
    container_name: mem0-mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
      - ./scripts/init_user_profile_mongodb.js:/docker-entrypoint-initdb.d/init.js
    networks:
      - mem0_network

  mem0-service:
    # ... existing config ...
    environment:
      # ... existing env vars ...
      - MONGODB_URI=mongodb://mongodb:27017
      - MONGODB_DATABASE=mem0_profile
    depends_on:
      - postgres
      - mongodb  # new dependency

volumes:
  postgres_db:
  mongodb_data:  # new
  neo4j_data:

networks:
  mem0_network:
    driver: bridge
```

### 10.3 .env.example Updates

```bash
# ... existing config ...

# MongoDB Configuration (for UserProfile)
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=mem0_profile
```

---

## Appendix A: Complete Code Examples

Due to length constraints, complete code is available in each module's implementation file.

---

## Appendix B: Frequently Asked Questions

**Q1: Why doesn't basic_info need a two-stage LLM process?**
A: Because basic_info field values are unique (e.g., current_city has only one value). When a new value is extracted it is directly overwritten, requiring no complex merge logic.

**Q2: What happens if the LLM returns malformed JSON?**
A: Four layers of fault tolerance protect against this. See Section 7.

**Q3: Can interests and skills overlap?**
A: Yes. The same item (e.g., "football") can appear in both interests and skills simultaneously.

**Q4: How is degree adjusted dynamically?**
A: The Stage 2 LLM evaluates evidence volume, quality, and temporal distribution to determine the degree.

**Q5: When will the vocabulary feature be developed?**
A: In the next phase. See `archived/vocab_design.md`.

---

**End of document**

**Next step**: Begin Phase 1 development!
