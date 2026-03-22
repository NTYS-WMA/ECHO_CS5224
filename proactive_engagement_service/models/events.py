"""
Event models published by the Proactive Engagement Service to the
Internal Asynchronous Messaging Layer.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OutboundResponseItem(BaseModel):
    """A single response item in the outbound event."""

    type: str = Field(
        default="text",
        description="Response type.",
        examples=["text"],
    )
    content: str = Field(
        ...,
        description="Message content.",
        examples=["Hey Alice, just checking in—how has your week been so far?"],
    )


class ProactiveOutboundEvent(BaseModel):
    """
    Published to topic: conversation.outbound

    Emitted for each proactive message that should be delivered to a user.
    Consumed by Channel Gateway / Channel Delivery Worker for outbound delivery.
    """

    event_id: str = Field(
        ...,
        description="Unique event identifier.",
        examples=["evt-7002"],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID linking back to the scan trigger.",
        examples=["evt-7001"],
    )
    event_type: str = Field(
        default="conversation.reply.generated",
        description="Event type discriminator.",
    )
    schema_version: str = Field(
        default="1.0",
        description="Schema version for forward compatibility.",
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp of the event.",
    )
    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    channel: str = Field(
        ...,
        description="Delivery channel.",
        examples=["telegram"],
    )
    conversation_id: str = Field(
        ...,
        description="Conversation identifier for delivery routing.",
        examples=["telegram-chat-123456789"],
    )
    responses: List[OutboundResponseItem] = Field(
        ...,
        description="List of response items to deliver.",
    )
    metadata: Optional[dict] = Field(
        None,
        description="Additional metadata for the outbound event.",
    )


class ProactiveDispatchCompletedEvent(BaseModel):
    """
    Published to topic: proactive.dispatch.completed

    Emitted after a proactive scan completes for telemetry and monitoring.
    """

    event_id: str = Field(
        ...,
        description="Unique event identifier.",
        examples=["evt-7003"],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID linking back to the scan trigger.",
        examples=["evt-7001"],
    )
    event_type: str = Field(
        default="proactive.dispatch.completed",
        description="Event type discriminator.",
    )
    schema_version: str = Field(
        default="1.0",
        description="Schema version for forward compatibility.",
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp of completion.",
    )
    stats: dict = Field(
        ...,
        description="Dispatch statistics.",
        examples=[
            {
                "candidates_scanned": 500,
                "messages_dispatched": 127,
                "messages_skipped": 373,
            }
        ],
    )
