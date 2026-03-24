"""
Client for the Relationship Service.

GET /api/v1/relationships/{user_id}/context

Note: The Relationship Service processes interactions on a 15-min scheduler
cycle (session-based scoring), not per-message. The Orchestrator publishes
relationship.interaction.recorded events to the event bus, which the
Relationship Service picks up on its own schedule.

Falls back to mock responses when MOCK_SERVICES=true.
"""

import logging
from typing import Any, Optional

import httpx

from shared.config.settings import settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=settings.relationship_service_url,
            timeout=10.0,
        )
    return _http_client


#Mock Data

def _mock_relationship(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "affinity_score": 0.55,
        "tier": "friend",
        "interaction_count": 42,
        "last_interaction_at": "2026-03-11T15:10:03Z",
        "decay_state": {
            "last_decay_at": "2026-03-12T00:00:00Z",
            "days_inactive": 0,
        },
        "updated_at": "2026-03-12T00:00:00Z",
    }


#Public API

async def get_relationship_context(user_id: str) -> Optional[dict[str, Any]]:
    """
    Fetch relationship context (affinity score, tier, decay state).

    Returns the relationship dict or None on failure.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Returning mock relationship for %s", user_id)
        return _mock_relationship(user_id)

    try:
        client = _get_client()
        resp = await client.get(f"/api/v1/relationships/{user_id}/context")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info("No relationship record for %s — new user", user_id)
            return _mock_relationship(user_id)  # default for new users
        logger.error("Relationship service error for %s: %s", user_id, e)
        return None
    except Exception:
        logger.exception("Failed to fetch relationship for %s", user_id)
        return None
