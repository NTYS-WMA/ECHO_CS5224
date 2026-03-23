"""
Client for the User Profile Service.

GET  /api/v1/users/{user_id}/profile
PATCH /api/v1/users/{user_id}/profile
POST /api/v1/users/{user_id}/onboarding/transitions

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
            base_url=settings.user_profile_service_url,
            timeout=10.0,
        )
    return _http_client


#Mock Data

def _mock_profile(user_id: str, username: str = "alice123") -> dict[str, Any]:
    return {
        "user_id": user_id,
        "external_user_id": f"telegram:mock",
        "channel": "telegram",
        "display_name": username.capitalize() if username else "User",
        "username": username,
        "language": "en",
        "timezone": "Asia/Singapore",
        "onboarding": {
            "state": "completed",
            "completed_at": "2026-03-10T09:00:00Z",
        },
        "preferences": {
            "tone": "friendly",
            "interests": ["general"],
            "quiet_hours": {
                "start": "22:00",
                "end": "07:00",
            },
        },
        "consent": {
            "personalization": True,
            "proactive_messaging": True,
            "analytics": True,
        },
        "account_tier": "free",
        "created_at": "2026-03-09T14:00:00Z",
        "updated_at": "2026-03-11T15:10:01Z",
    }


# Public API

async def get_user_profile(user_id: str, username: str = "") -> Optional[dict[str, Any]]:
    """
    Fetch user profile from User Profile Service.

    Returns the profile dict or None on failure.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Returning mock profile for %s", user_id)
        return _mock_profile(user_id, username)

    try:
        client = _get_client()
        resp = await client.get(f"/api/v1/users/{user_id}/profile")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info("Profile not found for %s — new user", user_id)
            return None
        logger.error("Profile service error for %s: %s", user_id, e)
        return None
    except Exception:
        logger.exception("Failed to fetch profile for %s", user_id)
        return None


async def upsert_user_profile(user_id: str, data: dict[str, Any]) -> bool:
    """
    Create or update user profile via PATCH.

    Returns True on success.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Upsert profile for %s", user_id)
        return True

    try:
        client = _get_client()
        resp = await client.patch(f"/api/v1/users/{user_id}/profile", json=data)
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed to upsert profile for %s", user_id)
        return False
