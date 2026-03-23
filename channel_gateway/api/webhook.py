"""
Channel Gateway — Telegram Webhook Endpoint
============================================

POST /api/v1/channels/telegram/webhook

Receives raw Telegram updates, validates them, normalizes into the internal
ConversationMessageReceivedEvent format, and publishes to the event bus.

Returns HTTP 200 immediately after successful validation + publish so
Telegram doesn't retry.
"""

import hashlib
import logging

from fastapi import APIRouter, Request, HTTPException

from channel_gateway.models.telegram import TelegramUpdate
from shared.events.event_bus import event_bus
from shared.events.topics import CONVERSATION_MESSAGE_RECEIVED
from shared.models.events import (
    ConversationMessageReceivedEvent,
    MessagePayload,
    MessageContext,
    _new_event_id,
    _utcnow,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/channels/telegram", tags=["Channel Gateway"])


# Helpers

def _derive_user_id(telegram_user_id: int) -> str:
    """
    Deterministic internal user ID from Telegram user ID.

    In production this would be a lookup/upsert against User Profile Service.
    For now we derive a stable short hash so the same Telegram user always
    maps to the same internal ID.
    """
    raw = f"telegram:{telegram_user_id}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"usr_{short_hash}"


def _detect_command(text: str) -> bool:
    """Check if the message is a bot command like /start, /help, /status."""
    return text.strip().startswith("/")


# Commands

COMMAND_RESPONSES = {
    "/start": "👋 Hey there! I'm ECHO, your friendly companion. Just say hi and we can chat!",
    "/help": "💡 Just send me a message and I'll respond! Commands:\n/start — Restart\n/help — This message\n/status — Check status",
    "/status": "✅ ECHO is online and ready to chat.",
}


#Webhook Endpoint

@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receive a Telegram update, normalize it, and publish to the event bus.

    For bot commands (/start, /help, /status), we respond inline without
    going through the full orchestration pipeline.
    """
    # Parse raw body — Telegram sends JSON
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Validate against our Telegram model
    try:
        update = TelegramUpdate(**body)
    except Exception as e:
        logger.warning("Failed to parse Telegram update: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid Telegram update: {e}")

    # We only handle message updates for now
    if update.message is None:
        logger.debug("Ignoring non-message update %d", update.update_id)
        return {"ok": True, "detail": "Ignored (no message)"}

    msg = update.message
    sender = msg.from_

    # Skip messages without text (photos, stickers, etc. — future work)
    if not msg.text:
        logger.debug("Ignoring non-text message %d", msg.message_id)
        return {"ok": True, "detail": "Ignored (non-text)"}

    # Handle bot commands inline
    text = msg.text.strip()
    if _detect_command(text):
        command = text.split()[0].lower()
        # Strip @botname suffix if present (e.g., /help@EchoBot)
        command = command.split("@")[0]
        reply_text = COMMAND_RESPONSES.get(
            command,
            f"🤔 Unknown command: {command}. Try /help.",
        )

        # Import here to avoid circular imports at module level
        from channel_gateway.workers.outbound_worker import send_telegram_message
        await send_telegram_message(chat_id=msg.chat.id, text=reply_text)

        logger.info("Handled command '%s' from chat %d", command, msg.chat.id)
        return {"ok": True, "detail": f"Command handled: {command}"}

    # Normalize into internal event
    telegram_user_id = sender.id if sender else msg.chat.id
    user_id = _derive_user_id(telegram_user_id)

    event = ConversationMessageReceivedEvent(
        event_id=_new_event_id(),
        timestamp=_utcnow(),
        user_id=user_id,
        external_user_id=f"telegram:{telegram_user_id}",
        channel="telegram",
        conversation_id=f"telegram-chat-{msg.chat.id}",
        channel_message_id=f"tg-{msg.message_id}",
        message=MessagePayload(
            role="user",
            type="text",
            content=text,
        ),
        context=MessageContext(
            command=False,
            received_at=_utcnow(),
            platform_user_id=str(telegram_user_id),
            platform_chat_id=str(msg.chat.id),
            username=sender.username if sender else "",
        ),
    )

    #Publish to internal event bus
    await event_bus.publish(CONVERSATION_MESSAGE_RECEIVED, event.model_dump())

    logger.info(
        "Published conversation.message.received — event_id=%s user=%s chat=%d",
        event.event_id,
        user_id,
        msg.chat.id,
    )

    # Return 200 immediately so Telegram doesn't retry
    return {"ok": True}
