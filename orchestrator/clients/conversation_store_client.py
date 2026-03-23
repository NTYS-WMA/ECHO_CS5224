"""
Client for the Conversation Persistence Store.

POST /api/v1/conversations/{conversation_id}/messages

Falls back to an in-memory store when MOCK_SERVICES=true, which also
serves as the short-term context source until the real store is wired up.
"""

import logging
from collections import defaultdict
from typing import Any, Optional

import httpx

from shared.config.settings import settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None

# In-Memory Store (mock mode + short-term context)
# conversation_id → list of message dicts
_in_memory_store: dict[str, list[dict[str, Any]]] = defaultdict(list)


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=settings.conversation_store_url,
            timeout=10.0,
        )
    return _http_client


#Public API

async def persist_messages(
    conversation_id: str,
    user_id: str,
    channel: str,
    messages: list[dict[str, Any]],
    correlation_id: str = "",
) -> bool:
    """
    Persist conversation messages (user + assistant turns).

    In mock mode, stores in memory so we can retrieve recent context.
    """
    # Always store in memory for short-term context retrieval
    _in_memory_store[conversation_id].extend(messages)

    if settings.mock_services:
        logger.debug(
            "[MOCK] Persisted %d message(s) for conversation %s (in-memory, total=%d)",
            len(messages),
            conversation_id,
            len(_in_memory_store[conversation_id]),
        )
        return True

    payload = {
        "user_id": user_id,
        "channel": channel,
        "messages": messages,
        "correlation_id": correlation_id,
    }

    try:
        client = _get_client()
        resp = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json=payload,
        )
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed to persist messages for %s", conversation_id)
        return False


async def get_recent_messages(
    conversation_id: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """
    Retrieve recent messages for short-term context.

    In mock mode (or when the real store isn't available), uses the
    in-memory store which captures everything persisted this session.
    """
    stored = _in_memory_store.get(conversation_id, [])
    recent = stored[-limit:] if stored else []
    logger.debug(
        "Retrieved %d recent messages for %s (in-memory store has %d total)",
        len(recent),
        conversation_id,
        len(stored),
    )
    return recent


def get_conversation_length(conversation_id: str) -> int:
    """Return total message count for a conversation (for summarization threshold check)."""
    return len(_in_memory_store.get(conversation_id, []))
