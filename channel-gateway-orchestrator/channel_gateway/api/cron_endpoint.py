"""
Cron Service Callback Endpoint
================================

The cron service calls POST /api/v1/cron/trigger with a CronTriggeredEvent
envelope when a scheduled task is due. User data is nested inside `payload`.
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cron", tags=["Cron"])


class CronTriggeredEvent(BaseModel):
    """Matches the CronTriggeredEvent schema from cron service v4.0."""
    event_id: str
    event_type: str
    source: str
    schema_version: str = "4.0"
    scheduled_event_id: Optional[str] = None
    event_name: Optional[str] = None
    caller_service: Optional[str] = None
    payload: dict[str, Any] = {}
    correlation_id: Optional[str] = None
    group_key: Optional[str] = None


@router.post("/trigger")
async def cron_trigger(event: CronTriggeredEvent):
    """
    Called by the cron service when a scheduled follow-up is due.

    The cron service sends a full CronTriggeredEvent envelope.
    User data (user_id, conversation_id, context) is inside event.payload.
    """
    from orchestrator.workers.orchestration_worker import handle_proactive_message

    payload = event.payload
    user_id = payload.get("user_id", "")
    conversation_id = payload.get("conversation_id", "")
    external_user_id = payload.get("external_user_id", "")
    context = payload.get("context", "")

    if not user_id or not conversation_id or not context:
        logger.error("Cron trigger missing required fields — payload: %s", payload)
        raise HTTPException(status_code=400, detail="Missing user_id, conversation_id or context in payload")

    logger.info(
        "Cron trigger received — user=%s conv=%s context='%s'",
        user_id, conversation_id, context[:80],
    )

    asyncio.create_task(handle_proactive_message(
        user_id=user_id,
        conversation_id=conversation_id,
        external_user_id=external_user_id,
        context=context,
    ))

    return {"status": "accepted", "user_id": user_id}
