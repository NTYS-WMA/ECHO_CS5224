"""
Event models for the Proactive Engagement Service v2.0.

Defines event payloads published to the Internal Messaging Layer
when tasks are dispatched or when lifecycle changes occur.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskDispatchedEvent(BaseModel):
    """
    Event published to topic: proactive.task.dispatched

    Emitted when a scheduled task is successfully dispatched to the
    Message Dispatch Hub.
    """

    event_id: str = Field(..., description="Unique event identifier.")
    event_type: str = Field(
        default="proactive.task.dispatched",
        description="Event type discriminator.",
    )
    schema_version: str = Field(default="2.0", description="Schema version.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC).",
    )
    task_id: str = Field(..., description="Task identifier.")
    user_id: str = Field(..., description="Target user identifier.")
    channel: str = Field(..., description="Target delivery channel.")
    conversation_id: Optional[str] = Field(None, description="Target conversation ID.")
    owner_service: str = Field(..., description="Registrant service name.")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing.")


class TaskFailedEvent(BaseModel):
    """
    Event published to topic: proactive.task.failed

    Emitted when a scheduled task exhausts all retries and is marked
    as permanently failed.
    """

    event_id: str = Field(..., description="Unique event identifier.")
    event_type: str = Field(
        default="proactive.task.failed",
        description="Event type discriminator.",
    )
    schema_version: str = Field(default="2.0", description="Schema version.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC).",
    )
    task_id: str = Field(..., description="Task identifier.")
    user_id: str = Field(..., description="Target user identifier.")
    owner_service: str = Field(..., description="Registrant service name.")
    error: str = Field(..., description="Error description.")
    retry_count: int = Field(..., description="Number of retries attempted.")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing.")


class OutboundMessagePayload(BaseModel):
    """
    Payload sent to the Message Dispatch Hub for outbound delivery.

    Published to topic: conversation.outbound
    """

    event_id: str = Field(..., description="Unique event identifier.")
    event_type: str = Field(
        default="conversation.outbound",
        description="Event type discriminator.",
    )
    schema_version: str = Field(default="2.0", description="Schema version.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC).",
    )
    task_id: str = Field(..., description="Source task identifier.")
    user_id: str = Field(..., description="Target user identifier.")
    channel: str = Field(..., description="Target delivery channel.")
    conversation_id: Optional[str] = Field(None, description="Target conversation ID.")
    message_type: str = Field(
        default="text",
        description="Message type: text, template, rich.",
    )
    content: Optional[str] = Field(None, description="Text content.")
    template_id: Optional[str] = Field(None, description="Template ID if template-based.")
    template_variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Template variables if template-based.",
    )
    attachments: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Optional attachments.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata from the registrant.",
    )
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing.")
