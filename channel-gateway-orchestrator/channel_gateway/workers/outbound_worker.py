"""
Channel Gateway — Outbound Delivery Worker
===========================================

Subscribes to: conversation.outbound

Consumes channel-agnostic reply events from the Orchestrator (or Proactive
Engagement Service) and delivers them to the appropriate Telegram chat via
the Telegram Bot API.
"""

import logging
from typing import Any

import httpx

from shared.config.settings import settings
from shared.events.event_bus import event_bus
from shared.events.topics import CONVERSATION_OUTBOUND

logger = logging.getLogger(__name__)

# Reusable async HTTP client for Telegram API calls
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


#Telegram Send

async def send_telegram_message(chat_id: int, text: str) -> bool:
    """
    Send a text message via Telegram Bot API — sendMessage.

    Returns True on success, False on failure.
    """
    token = settings.telegram_bot_token
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — message not delivered to chat %d", chat_id)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        client = _get_http_client()
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        logger.info("Delivered message to Telegram chat %d", chat_id)
        return True
    except httpx.HTTPStatusError as e:
        logger.error(
            "Telegram API error for chat %d: %s — %s",
            chat_id,
            e.response.status_code,
            e.response.text[:300],
        )
        return False
    except Exception:
        logger.exception("Failed to send message to Telegram chat %d", chat_id)
        return False


# Event Handler

async def handle_outbound_event(event: dict[str, Any]) -> None:
    """
    Process a conversation.outbound event.

    Extracts the target chat ID from the conversation_id, formats each
    response item, and sends via Telegram.
    """
    conversation_id: str = event.get("conversation_id", "")
    responses: list[dict] = event.get("responses", [])
    event_id = event.get("event_id", "?")

    # Derive Telegram chat ID from conversation_id (format: "telegram-chat-{chat_id}")
    try:
        chat_id = int(conversation_id.replace("telegram-chat-", ""))
    except (ValueError, AttributeError):
        logger.error("Cannot extract chat_id from conversation_id=%s", conversation_id)
        return

    if not responses:
        logger.warning("Outbound event %s has no responses — nothing to deliver", event_id)
        return

    # Deliver each response item (usually just one text message)
    for resp_item in responses:
        resp_type = resp_item.get("type", "text")
        content = resp_item.get("content", "")

        if resp_type == "text" and content:
            success = await send_telegram_message(chat_id, content)
            if success:
                logger.info("Delivered outbound event %s to chat %d", event_id, chat_id)
            else:
                logger.error("Failed to deliver outbound event %s to chat %d", event_id, chat_id)
        else:
            # Future: handle audio, image, etc.
            logger.warning("Unsupported response type '%s' in event %s — skipped", resp_type, event_id)


#Registration

def register_outbound_worker() -> None:
    """Subscribe the outbound delivery handler to the event bus."""
    event_bus.subscribe(CONVERSATION_OUTBOUND, handle_outbound_event)
    logger.info("Outbound delivery worker registered on topic '%s'", CONVERSATION_OUTBOUND)
