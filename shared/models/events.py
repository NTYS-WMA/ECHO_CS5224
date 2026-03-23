"""
Shared event models used by both Channel Gateway and Orchestrator.

These match the payload schemas defined in the architecture document.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


#Helpers

def _new_event_id() -> str:
    return f"evt-{uuid.uuid4().hex[:12]}"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


#Message Sub-models

class MessagePayload(BaseModel):
    """Content of a single message within an event."""
    role: str  # "user" or "assistant"
    type: str = "text"
    content: str


class MessageContext(BaseModel):
    """Channel-specific metadata attached to an inbound event."""
    command: bool = False
    received_at: str = Field(default_factory=_utcnow)
    platform_user_id: str = ""
    platform_chat_id: str = ""
    username: str = ""


#Inbound Conversation Event

class ConversationMessageReceivedEvent(BaseModel):
    """
    Published by Channel Gateway to topic: conversation.message.received

    Consumed by Conversation Orchestrator to start the reply workflow.
    """
    event_id: str = Field(default_factory=_new_event_id)
    event_type: str = "conversation.message.received"
    timestamp: str = Field(default_factory=_utcnow)
    user_id: str
    external_user_id: str  # e.g. "telegram:123456789"
    channel: str = "telegram"
    conversation_id: str
    channel_message_id: str
    message: MessagePayload
    context: MessageContext


#Outbound Reply Event

class ResponseItem(BaseModel):
    type: str = "text"
    content: str


class ConversationOutboundEvent(BaseModel):
    """
    Published by Conversation Orchestrator to topic: conversation.outbound

    Consumed by Channel Gateway outbound worker to deliver via Telegram.
    """
    event_id: str = Field(default_factory=_new_event_id)
    correlation_id: str = ""
    event_type: str = "conversation.reply.generated"
    timestamp: str = Field(default_factory=_utcnow)
    user_id: str
    external_user_id: str
    channel: str = "telegram"
    conversation_id: str
    responses: list[ResponseItem]
    metadata: dict[str, Any] = Field(default_factory=dict)


#Relationship Interaction Event

class RelationshipInteractionEvent(BaseModel):
    """
    Published by Orchestrator to topic: relationship.interaction.recorded

    The Relationship Service consumes these on its 15-min scheduler cycle
    for session-based scoring (not per-message processing).
    """
    event_id: str = Field(default_factory=_new_event_id)
    correlation_id: str = ""
    event_type: str = "relationship.interaction.recorded"
    timestamp: str = Field(default_factory=_utcnow)
    user_id: str
    external_user_id: str
    channel: str = "telegram"
    conversation_id: str
    sentiment: str = "neutral"  # positive / neutral / negative
    message_count_delta: int = 1
    last_message_at: str = Field(default_factory=_utcnow)


#Memory Summarization Request

class MemorySummaryRequestedEvent(BaseModel):
    """
    Published by Orchestrator to topic: memory.summary.requested

    Consumed by Memory Service to trigger conversation window summarization.
    """
    event_id: str = Field(default_factory=_new_event_id)
    correlation_id: str = ""
    event_type: str = "memory.summary.requested"
    timestamp: str = Field(default_factory=_utcnow)
    user_id: str
    conversation_id: str
    window: dict[str, str] = Field(default_factory=dict)
    trigger: str = "conversation_length_threshold"


#Processing Failure Event

class ConversationProcessingFailedEvent(BaseModel):
    """
    Published by Orchestrator to topic: conversation.processing.failed

    Used for monitoring, alerting, and retry logic.
    """
    event_id: str = Field(default_factory=_new_event_id)
    correlation_id: str = ""
    event_type: str = "conversation.processing.failed"
    timestamp: str = Field(default_factory=_utcnow)
    user_id: str
    external_user_id: str
    conversation_id: str
    stage: str  # e.g. "ai_generation", "memory_retrieval", "profile_lookup"
    error_code: str
    retryable: bool = True
