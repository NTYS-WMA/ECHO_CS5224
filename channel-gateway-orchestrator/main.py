"""
ECHO — Channel Gateway & Conversation Orchestrator
====================================================

Main entrypoint. Starts the FastAPI server with:
- Telegram webhook endpoint (Channel Gateway)
- Outbound delivery worker (Channel Gateway)
- Orchestration worker (Conversation Orchestrator)
- Health check / debug endpoints
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from shared.config.settings import settings
from shared.events.event_bus import event_bus

#Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("echo")


#Lifespan: Wire up event bus subscribers on startup

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Register all event-bus workers on startup, clean up on shutdown."""
    logger.info("=" * 60)
    logger.info("ECHO starting up")
    logger.info("  Mock services: %s", settings.mock_services)
    logger.info("  Telegram token: %s", "SET" if settings.telegram_bot_token else "NOT SET")
    logger.info("  Memory service: %s", settings.memory_service_url)
    logger.info("=" * 60)

    # Register the orchestration worker (consumes conversation.message.received)
    from orchestrator.workers.orchestration_worker import register_orchestration_worker
    await register_orchestration_worker()

    # Register the outbound delivery worker (consumes conversation.outbound)
    from channel_gateway.workers.outbound_worker import register_outbound_worker
    register_outbound_worker()

    logger.info("All workers registered. Active topics: %s", event_bus.list_topics())

    yield  # App is running

    logger.info("ECHO shutting down")


#FastAPI App
app = FastAPI(
    title="ECHO — Channel Gateway & Orchestrator",
    description=(
        "Receives Telegram webhooks, orchestrates reply generation "
        "using profile/memory/relationship context, and delivers replies."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


#Include Routers

from channel_gateway.api.webhook import router as telegram_router
app.include_router(telegram_router)


#Health & Debug Endpoints

@app.get("/health", tags=["System"])
async def health():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "echo-gateway-orchestrator",
        "mock_mode": settings.mock_services,
    }


@app.get("/debug/event-bus", tags=["System"])
async def debug_event_bus():
    """Show registered event bus topics and subscriber counts."""
    return {
        "topics": {
            topic: len(event_bus._subscribers[topic])
            for topic in event_bus.list_topics()
        }
    }


@app.get("/debug/conversations", tags=["System"])
async def debug_conversations():
    """Show in-memory conversation store state (mock mode only)."""
    from orchestrator.clients.conversation_store_client import _in_memory_store
    return {
        conv_id: {
            "message_count": len(msgs),
            "last_message": msgs[-1] if msgs else None,
        }
        for conv_id, msgs in _in_memory_store.items()
    }


#Simulate Endpoint (for testing without Telegram)

@app.post("/debug/simulate", tags=["System"])
async def simulate_message(user_id: str = "usr_test001", text: str = "Hello ECHO"):
    """
    Simulate an inbound message without going through Telegram.

    Useful for testing the orchestration pipeline end-to-end.
    Publishes a conversation.message.received event directly.
    """
    from shared.events.topics import CONVERSATION_MESSAGE_RECEIVED
    from shared.models.events import (
        ConversationMessageReceivedEvent,
        MessagePayload,
        MessageContext,
        _new_event_id,
        _utcnow,
    )

    event = ConversationMessageReceivedEvent(
        event_id=_new_event_id(),
        timestamp=_utcnow(),
        user_id=user_id,
        external_user_id=f"telegram:simulated",
        channel="telegram",
        conversation_id=f"telegram-chat-simulated-{user_id}",
        channel_message_id="tg-sim-1",
        message=MessagePayload(role="user", type="text", content=text),
        context=MessageContext(
            command=False,
            received_at=_utcnow(),
            platform_user_id="simulated",
            platform_chat_id="simulated",
            username="test_user",
        ),
    )

    await event_bus.publish(CONVERSATION_MESSAGE_RECEIVED, event.model_dump())

    return {
        "status": "published",
        "event_id": event.event_id,
        "detail": "Check logs for orchestration flow. Reply will attempt Telegram delivery (will fail for simulated chat).",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
