"""
Client for conversation message persistence.

Messages are written to db-manager (port 18087) which stores them in PostgreSQL.
This makes conversation history persistent across container restarts.

The in-memory store is always kept in sync as a same-session fallback
and for the summarization threshold counter.

db-manager endpoints used:
  PUT /relationship-db/users/{user_id}   — ensure user exists (FK requirement)
  POST /relationship-db/messages         — insert a message
  GET  /relationship-db/messages         — retrieve recent messages by user_id

Falls back to in-memory when MOCK_SERVICES=true or db-manager is unavailable.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from shared.config.settings import settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None

# In-memory store — always written; serves short-term context + summarization counter
_in_memory_store: dict[str, list[dict[str, Any]]] = defaultdict(list)


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        headers = {}
        if settings.db_manager_api_key:
            headers["X-API-Key"] = settings.db_manager_api_key
        _http_client = httpx.AsyncClient(
            base_url=settings.db_manager_url,
            headers=headers,
            timeout=10.0,
        )
    return _http_client


# Public API

async def ensure_user_registered(
    user_id: str,
    telegram_id: Optional[int] = None,
    first_name: Optional[str] = None,
) -> None:
    """
    Upsert the user row in db-manager before any messages are inserted.

    The messages table has a foreign key on users.id, so the user row must
    exist first or the message insert will fail with an IntegrityError.
    Failures here are non-fatal — the message insert will surface the error.
    """
    if settings.mock_services:
        return

    try:
        client = _get_client()
        payload: dict[str, Any] = {
            "last_active_at": datetime.now(timezone.utc).isoformat(),
            "onboarding_complete": True,
        }
        if telegram_id is not None:
            payload["telegram_id"] = telegram_id
        if first_name:
            payload["first_name"] = first_name
        resp = await client.put(f"/relationship-db/users/{user_id}", json=payload)
        resp.raise_for_status()
        logger.debug("Upserted user %s in db-manager", user_id)
    except Exception:
        logger.warning("Failed to upsert user %s in db-manager (non-fatal)", user_id)


async def persist_messages(
    conversation_id: str,
    user_id: str,
    channel: str,
    messages: list[dict[str, Any]],
    correlation_id: str = "",
) -> bool:
    """
    Persist conversation messages to db-manager (PostgreSQL) and the in-memory store.

    In mock mode, writes only to the in-memory store.
    """
    # Always write to memory for same-session short-term context and length tracking
    _in_memory_store[conversation_id].extend(messages)

    if settings.mock_services:
        logger.debug(
            "[MOCK] Persisted %d message(s) for conversation %s (in-memory only, total=%d)",
            len(messages),
            conversation_id,
            len(_in_memory_store[conversation_id]),
        )
        return True

    success = True
    try:
        client = _get_client()
        for msg in messages:
            payload: dict[str, Any] = {
                "user_id": user_id,
                "role": msg.get("role"),
                "content": msg.get("content"),
                "is_proactive": False,
            }
            ts = msg.get("timestamp")
            if ts:
                payload["created_at"] = ts

            resp = await client.post("/relationship-db/messages", json=payload)
            resp.raise_for_status()

        logger.debug(
            "Persisted %d message(s) for user %s to db-manager",
            len(messages),
            user_id,
        )
    except Exception:
        logger.exception(
            "Failed to persist messages to db-manager for user %s (in-memory fallback active)",
            user_id,
        )
        success = False

    return success


async def get_recent_messages(
    conversation_id: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """
    Retrieve recent messages for short-term context from the in-memory store.

    Messages are persisted to db-manager for the relationship service's scoring
    cycle, but short-term context is served from memory to avoid adding latency
    to the AI generation path.
    """
    stored = _in_memory_store.get(conversation_id, [])
    recent = stored[-limit:] if stored else []
    logger.debug(
        "Retrieved %d recent messages for %s (in-memory, total stored=%d)",
        len(recent),
        conversation_id,
        len(stored),
    )
    return recent


def get_conversation_length(conversation_id: str) -> int:
    """Return total message count for a conversation (for summarization threshold check)."""
    return len(_in_memory_store.get(conversation_id, []))


async def write_cron_task(
    user_id: str,
    conversation_id: str,
    external_user_id: str,
    context: str,
    delay_minutes: int,
) -> bool:
    """
    Register a one-time scheduled event in db-manager.

    The cron service polls /scheduled-events/due/poll every 30s and
    calls back to POST /api/v1/cron/trigger on this service when due.
    """
    if settings.mock_services:
        logger.debug("[MOCK] Cron task scheduled for %s in %d min: %s", user_id, delay_minutes, context)
        return True

    try:
        scheduled_at = (datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)).isoformat()

        client = _get_client()
        payload = {
            "event_name": f"chloe-followup-{user_id}",
            "event_type": "one_time",
            "caller_service": "channel-gateway-orchestrator",
            "callback_url": f"{settings.service_base_url}/api/v1/cron/trigger",
            "scheduled_at": scheduled_at,
            "next_fire_at": scheduled_at,
            "payload": {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "external_user_id": external_user_id,
                "context": context,
            },
            "group_key": user_id,
            "correlation_id": conversation_id,
        }
        resp = await client.post("/scheduled-events", json=payload)
        resp.raise_for_status()
        logger.info("Cron task registered for %s, due at %s", user_id, scheduled_at)
        return True
    except Exception:
        logger.exception("Failed to write cron task for %s", user_id)
        return False
