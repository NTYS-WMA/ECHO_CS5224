# Proactive Engagement Service

The Proactive Engagement Service determines when ECHO should initiate outbound engagement with users. It manages the full pipeline from candidate selection through policy checking to message dispatch, ensuring that proactive outreach is timely, personalized, and respectful of user preferences.

---

## Architecture Position

```
Platform Scheduler ──▶ proactive.scan.requested (Event)
                              │
                              ▼
                 ┌──────────────────────────────┐
                 │ Proactive Engagement Service  │
                 │                              │
                 │  1. Search candidates        │◄──── Relationship Service
                 │  2. Check eligibility        │◄──── User Profile Service
                 │  3. Retrieve memory summary  │◄──── Memory Service (MyMem0)
                 │  4. Generate proactive msg   │◄──── AI Generation Service
                 │  5. Publish outbound event   │
                 └──────────┬───────────────────┘
                            │
             ┌──────────────┼──────────────┐
             ▼                             ▼
  conversation.outbound         proactive.dispatch.completed
        (Event)                        (Event)
             │
             ▼
  Channel Gateway / Delivery Worker
```

---

## Directory Structure

```
proactive_engagement_service/
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
│   ├── requests.py                 # Request and event payload models
│   ├── responses.py                # Response models
│   ├── domain.py                   # Internal domain models
│   └── events.py                   # Published event models
├── routes/
│   ├── __init__.py
│   ├── engagement_routes.py        # /api/v1/proactive/* endpoints
│   └── health_routes.py            # /health and /ready endpoints
├── services/
│   ├── __init__.py
│   ├── relationship_client.py      # HTTP client for Relationship Service
│   ├── user_profile_client.py      # HTTP client for User Profile Service
│   ├── ai_generation_client.py     # HTTP client for AI Generation Service
│   ├── memory_client.py            # HTTP client for Memory Service (MyMem0)
│   ├── eligibility_checker.py      # Consent and quiet-hours policy checker
│   └── engagement_service.py       # Core pipeline orchestration logic
├── events/
│   ├── __init__.py
│   ├── publisher.py                # Event publisher for messaging layer
│   └── consumer.py                 # Event consumer for scan triggers
├── utils/
│   ├── __init__.py
│   └── helpers.py                  # ID generation, quiet hours, tier mapping
└── tests/
    ├── __init__.py
    └── test_engagement.py          # Unit tests
```

---

## Pipeline Stages

The proactive engagement pipeline processes candidates through six stages:

| Stage | Description                                  | Dependency               |
|-------|----------------------------------------------|--------------------------|
| 1     | Search for proactive candidates              | Relationship Service     |
| 2     | Check eligibility (consent + quiet hours)    | User Profile Service     |
| 3     | Retrieve recent memory summary               | Memory Service (MyMem0)  |
| 4     | Generate AI proactive message                | AI Generation Service    |
| 5     | Publish outbound message event               | Messaging Layer          |
| 6     | Publish dispatch telemetry event             | Messaging Layer          |

Stage 3 (memory retrieval) is best-effort: if the Memory Service is unavailable, the message is generated without personalization context.

---

## API Endpoints

| Method | Endpoint                      | Source          | Description                    |
|--------|-------------------------------|-----------------|--------------------------------|
| POST   | `/api/v1/proactive/trigger`   | Operations      | Manually trigger a scan        |
| GET    | `/api/v1/proactive/status`    | Operations      | Service status and info        |
| GET    | `/health`                     | Infrastructure  | Liveness check                 |
| GET    | `/ready`                      | Infrastructure  | Readiness check                |

For detailed request/response schemas, see [API_INTERFACES.md](./API_INTERFACES.md).

---

## Consumed Events

| Topic                       | Source             | Description                    |
|-----------------------------|--------------------|--------------------------------|
| `proactive.scan.requested`  | Platform Scheduler | Triggers a proactive scan      |

---

## Published Events

| Topic                          | Consumer                  | Description                    |
|--------------------------------|---------------------------|--------------------------------|
| `conversation.outbound`        | Channel Gateway / Worker  | Proactive messages for delivery|
| `proactive.dispatch.completed` | Monitoring / Telemetry    | Scan completion statistics     |

---

## Configuration

All configuration is loaded from environment variables with the `PROACTIVE_` prefix. Key settings:

| Variable                                    | Default                 | Description                          |
|---------------------------------------------|-------------------------|--------------------------------------|
| `PROACTIVE_HOST`                            | `0.0.0.0`              | Service bind host                    |
| `PROACTIVE_PORT`                            | `8006`                 | Service bind port                    |
| `PROACTIVE_RELATIONSHIP_SERVICE_BASE_URL`   | `http://localhost:8004`| Relationship Service URL             |
| `PROACTIVE_USER_PROFILE_SERVICE_BASE_URL`   | `http://localhost:8002`| User Profile Service URL             |
| `PROACTIVE_AI_GENERATION_SERVICE_BASE_URL`  | `http://localhost:8003`| AI Generation Service URL            |
| `PROACTIVE_MEMORY_SERVICE_BASE_URL`         | `http://localhost:18088`| Memory Service (MyMem0) URL         |
| `PROACTIVE_EVENT_BROKER_URL`                | `redis://localhost:6379/0` | Event broker connection URL      |
| `PROACTIVE_DEFAULT_MIN_DAYS_INACTIVE`       | `3`                    | Default min inactivity days          |
| `PROACTIVE_DEFAULT_MIN_AFFINITY_SCORE`      | `0.5`                  | Default min affinity score           |
| `PROACTIVE_DEFAULT_MAX_BATCH_SIZE`          | `500`                  | Default max candidates per scan      |
| `PROACTIVE_DEFAULT_QUIET_HOURS_START`       | `22:00`                | Default quiet hours start            |
| `PROACTIVE_DEFAULT_QUIET_HOURS_END`         | `07:00`                | Default quiet hours end              |

See `config/settings.py` for the full list of configurable parameters.

---

## Running the Service

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn proactive_engagement_service.app:app --host 0.0.0.0 --port 8006

# Run tests
pytest proactive_engagement_service/tests/ -v
```

---

## Dependencies on Other Services

| Service                  | Interface Type        | Status          |
|--------------------------|-----------------------|-----------------|
| Relationship Service     | HTTP API              | TO BE UPDATED   |
| User Profile Service     | HTTP API              | TO BE UPDATED   |
| AI Generation Service    | HTTP API              | Defined         |
| Memory Service (MyMem0)  | HTTP API              | TO BE UPDATED   |
| Messaging Layer          | Event consume/publish | TO BE UPDATED   |
| Platform Scheduler       | Event publish         | TO BE UPDATED   |

For details on assumed interfaces, see [ASSUMED_INTERFACES.md](./ASSUMED_INTERFACES.md).
