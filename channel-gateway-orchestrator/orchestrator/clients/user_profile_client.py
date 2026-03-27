"""
Client for user profile data.

Profile data is served by the Memory Service (MyMem0) at the same base URL
as memory operations. The Memory Service extracts and maintains profile data
(basic info + interests/skills/personality) from conversation messages.

GET /profile?user_id={user_id}  → fetch profile
POST /profile                   → extract + update profile from messages (called via memory_client)

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
            base_url=settings.memory_service_url,  # Memory service hosts the profile API
            timeout=10.0,
        )
    return _http_client


# Mock Data

def _mock_profile(user_id: str, username: str = "") -> dict[str, Any]:
    return {
        "user_id": user_id,
        "display_name": username.capitalize() if username else "User",
        "language": "en",
        "timezone": "Asia/Singapore",
        "tone": "friendly",
        "interests": ["general"],
        "onboarding_state": "completed",
        "consent_personalization": True,
    }


def _parse_memory_profile(data: dict[str, Any], username: str = "") -> dict[str, Any]:
    """
    Normalise the Memory Service profile response into the flat structure
    the orchestrator expects.

    Memory Service returns:
      {
        "user_id": "...",
        "basic_info": { "name": ..., "timezone": ..., "language": ..., ... },
        "additional_profile": { "interests": [{"name": ..., ...}], ... }
      }
    """
    basic = data.get("basic_info") or {}
    additional = data.get("additional_profile") or {}

    # display_name: prefer name, then nickname, then username fallback
    display_name = (
        basic.get("name")
        or basic.get("nickname")
        or (username.capitalize() if username else "User")
    )

    # interests: list of name strings extracted from evidence-backed interest objects
    raw_interests = additional.get("interests") or []
    interests = [i.get("name") for i in raw_interests if i.get("name")]

    return {
        "user_id": data.get("user_id", ""),
        "display_name": display_name,
        "language": basic.get("language") or "en",
        "timezone": basic.get("timezone") or "UTC",
        "tone": "friendly",           # not tracked by memory service — use default
        "interests": interests,
        "onboarding_state": "completed",   # not tracked by memory service — use default
        "consent_personalization": True,   # not tracked by memory service — use default
    }


# Public API

async def get_user_profile(user_id: str, username: str = "") -> Optional[dict[str, Any]]:
    """
    Fetch user profile from the Memory Service.

    Returns a normalised profile dict or None on failure.
    On 404 (no profile extracted yet) returns None — orchestrator falls back to defaults.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Returning mock profile for %s", user_id)
        return _mock_profile(user_id, username)

    try:
        client = _get_client()
        resp = await client.get("/profile", params={"user_id": user_id})
        resp.raise_for_status()
        return _parse_memory_profile(resp.json(), username)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info("No profile found for %s — using defaults", user_id)
            return None
        logger.error("Profile fetch error for %s: %s", user_id, e)
        return None
    except Exception:
        logger.exception("Failed to fetch profile for %s", user_id)
        return None


async def upsert_user_profile(user_id: str, data: dict[str, Any]) -> bool:
    """
    Profile updates happen via POST /profile (messages-based extraction) in memory_client.
    This stub exists for interface compatibility.
    """
    if settings.mock_services:
        return True
    # Profile upsert is handled by memory_client.update_mymem0_profile (message-based)
    return True
