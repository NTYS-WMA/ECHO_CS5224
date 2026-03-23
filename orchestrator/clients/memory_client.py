"""
Client for the Memory Service (MyMem0).

This integrates with the Memory Service documented in the Internal Integration Guide:
  - POST /search         → semantic memory search (long-term retrieval)
  - GET  /memories       → list all memories for a user
  - POST /memories       → write new memories from conversation
  - POST /profile        → extract and update user profile from conversation
  - GET  /profile        → get user profile

Base URL: http://<host>:18088 (configured via MEMORY_SERVICE_URL)

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
            base_url=settings.memory_service_url,
            timeout=15.0,  # memory service can be slow due to LLM calls
        )
    return _http_client


#Mock Data

def _mock_memory_context(user_id: str, query: str) -> dict[str, Any]:
    return {
        "short_term": [
            {
                "message_id": "msg-mock-01",
                "role": "assistant",
                "content": "How's your day going?",
                "timestamp": "2026-03-11T14:56:00Z",
            }
        ],
        "long_term": [
            {
                "memory_id": "mem-mock-01",
                "content": "User enjoys casual conversations and checking in",
                "score": 0.85,
                "source": "summary",
            }
        ],
        "retrieval_metadata": {
            "short_term_count": 1,
            "long_term_count": 1,
        },
    }


#Public API: Memory Retrieval

async def get_memory_context(
    user_id: str,
    conversation_id: str,
    query: str,
    short_term_limit: int = 12,
    long_term_limit: int = 5,
) -> dict[str, Any]:
    """
    Retrieve both short-term and long-term memory context.

    This combines:
    1. Recent conversation turns (short-term) — for now from mock/store
    2. Semantic search over long-term memories via POST /search

    Returns a dict with 'short_term' and 'long_term' keys matching
    the Orchestrator's expected memory context format.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Returning mock memory context for %s", user_id)
        return _mock_memory_context(user_id, query)

    # Long-term: semantic search via MyMem0
    long_term = []
    try:
        client = _get_client()
        search_resp = await client.post("/search", json={
            "query": query,
            "user_id": user_id,
            "limit": long_term_limit,
            "threshold": 0.3,
        })
        search_resp.raise_for_status()
        search_data = search_resp.json()

        for item in search_data.get("results", []):
            long_term.append({
                "memory_id": item.get("id", ""),
                "content": item.get("memory", ""),
                "score": item.get("score", 0.0),
                "source": "vector_search",
            })
    except Exception:
        logger.exception("Long-term memory search failed for %s", user_id)

    # Short-term: placeholder
    # In the full architecture, short-term context comes from the
    # Conversation Persistence Store. For now we return an empty list
    # and the orchestrator handles the case gracefully.
    short_term: list[dict] = []

    return {
        "short_term": short_term,
        "long_term": long_term,
        "retrieval_metadata": {
            "short_term_count": len(short_term),
            "long_term_count": len(long_term),
        },
    }


# Public API: Write Memories

async def write_memories(
    user_id: str,
    messages: list[dict[str, str]],
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """
    Write new memories from conversation messages via POST /memories.

    The MyMem0 service uses LLM to extract facts and decides whether to
    ADD, UPDATE, or DELETE existing memories automatically.

    Args:
        user_id: Internal user ID
        messages: List of {"role": "user"/"assistant", "content": "..."}
        metadata: Optional metadata dict attached to memories

    Returns:
        The API response dict with 'results' or None on failure.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Write memories for %s", user_id)
        return {"results": []}

    try:
        client = _get_client()
        payload: dict[str, Any] = {
            "messages": messages,
            "user_id": user_id,
        }
        if metadata:
            payload["metadata"] = metadata

        resp = await client.post("/memories", json=payload)
        resp.raise_for_status()
        result = resp.json()
        logger.info(
            "Wrote memories for %s: %d operations",
            user_id,
            len(result.get("results", [])),
        )
        return result
    except Exception:
        logger.exception("Failed to write memories for %s", user_id)
        return None


#Public API: Update Profile via MyMem0

async def update_mymem0_profile(
    user_id: str,
    messages: list[dict[str, str]],
) -> Optional[dict[str, Any]]:
    """
    Extract and update user profile from conversation via POST /profile.

    This triggers two sequential LLM calls inside MyMem0:
    1. Extract profile fields from conversation
    2. Decide ADD/UPDATE/DELETE per field

    NOTE: This is slow (3-10 seconds). Call asynchronously / in background.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Update MyMem0 profile for %s", user_id)
        return {"success": True, "operations_performed": {"added": 0, "updated": 0, "deleted": 0}}

    try:
        client = _get_client()
        resp = await client.post("/profile", json={
            "messages": messages,
            "user_id": user_id,
        })
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("Failed to update MyMem0 profile for %s", user_id)
        return None
