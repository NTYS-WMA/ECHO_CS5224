"""
DB Manager — HTTP client for the Relationship Service.

All DB operations are delegated to the db-manager service via its REST API.
No direct database connection is held here.

Endpoint prefix: {db_manager_url}/relationship-db
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_BASE = f"{settings.db_manager_url}/relationship-db"
_HEADERS = {"X-API-Key": settings.db_manager_api_key} if settings.db_manager_api_key else {}


# ─── Internal helper ──────────────────────────────────────────────────────────


async def _put_score(user_id: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.put(f"{_BASE}/scores/{user_id}", json=payload, headers=_HEADERS)
        r.raise_for_status()


# ─── Users (read-only) ────────────────────────────────────────────────────────


async def get_user_by_id(user_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_BASE}/users/{user_id}", headers=_HEADERS)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def get_users_with_ended_sessions(inactive_minutes: int = 30) -> list[dict]:
    """
    Return flat dicts whose session has ended and not yet scored.
    Each dict contains combined user + relationship_score fields.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/users/ended-sessions",
            params={"inactive_minutes": inactive_minutes},
            headers=_HEADERS,
        )
        r.raise_for_status()
        return r.json()["results"]


async def get_inactive_users(inactive_hours: int) -> list[dict]:
    """Return onboarded users inactive for more than `inactive_hours`."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/users/inactive",
            params={"inactive_hours": inactive_hours},
            headers=_HEADERS,
        )
        r.raise_for_status()
        return r.json()["results"]


# ─── Messages (read-only) ─────────────────────────────────────────────────────


async def get_messages_since_datetime(
    user_id: str,
    since: Optional[datetime],
) -> list[dict]:
    """Return all messages for a user after `since`, in chronological order."""
    params: dict = {"user_id": user_id}
    if since is not None:
        params["since"] = since.isoformat()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_BASE}/messages", params=params, headers=_HEADERS)
        r.raise_for_status()
        return r.json()["results"]


# ─── Relationship Score (read/write) ─────────────────────────────────────────


async def get_relationship_score(user_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{_BASE}/scores/{user_id}", headers=_HEADERS)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def update_relationship_score(
    user_id: str,
    delta: float,
    is_positive: bool,
    is_decay: bool = False,
) -> float:
    """
    Adjust score by `delta` and return the new score.

    Fetches current score from db-manager, computes the new value locally,
    then PUTs the result back. Interaction counters are only incremented
    for real session scores, not decay.
    """
    rel = await get_relationship_score(user_id)
    if rel is None:
        rel = {
            "score": 0.10,
            "total_interactions": 0,
            "positive_interactions": 0,
            "negative_interactions": 0,
            "last_decay_at": None,
        }

    new_score = max(0.0, min(1.0, rel["score"] + delta))
    payload: dict = {
        "score": new_score,
        "total_interactions": rel["total_interactions"] + (0 if is_decay else 1),
        "positive_interactions": rel["positive_interactions"] + (1 if not is_decay and is_positive else 0),
        "negative_interactions": rel["negative_interactions"] + (1 if not is_decay and not is_positive else 0),
    }
    if is_decay:
        payload["last_decay_at"] = datetime.now(timezone.utc).isoformat()

    await _put_score(user_id, payload)
    return new_score


async def set_score_absolute(
    user_id: str,
    score: float,
    current_rel: Optional[dict] = None,
) -> None:
    """
    Set score to an exact value without touching interaction counters.

    Pass `current_rel` (from a prior get_relationship_score call) to avoid
    an extra round-trip.
    """
    if current_rel is None:
        current_rel = await get_relationship_score(user_id)
        if current_rel is None:
            return
    payload = {
        "score": max(0.0, min(1.0, score)),
        "total_interactions": current_rel["total_interactions"],
        "positive_interactions": current_rel["positive_interactions"],
        "negative_interactions": current_rel["negative_interactions"],
    }
    await _put_score(user_id, payload)


async def insert_score_history(
    user_id: str,
    delta: float,
    new_score: float,
    reason: str,
    sentiment: Optional[str] = None,
    intensity: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> None:
    payload = {
        "delta": delta,
        "new_score": new_score,
        "reason": reason,
        "sentiment": sentiment,
        "intensity": intensity,
        "reasoning": reasoning,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{_BASE}/scores/{user_id}/history", json=payload, headers=_HEADERS)
        r.raise_for_status()


async def stamp_last_scored_at(user_id: str) -> None:
    """Mark a session as scored so it is not re-evaluated on the next cron run."""
    rel = await get_relationship_score(user_id)
    if rel is None:
        return
    payload = {
        "score": rel["score"],
        "total_interactions": rel["total_interactions"],
        "positive_interactions": rel["positive_interactions"],
        "negative_interactions": rel["negative_interactions"],
        "last_scored_at": datetime.now(timezone.utc).isoformat(),
    }
    await _put_score(user_id, payload)
