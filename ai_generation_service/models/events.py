"""
Event models published by the AI Generation Service to the Internal Asynchronous Messaging Layer.

These events are used for monitoring, telemetry, and incident workflows.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GenerationFailedEvent(BaseModel):
    """
    Published to topic: ai.generation.failed

    Emitted when a generation request fails after all retry and fallback attempts.
    Consumed by observability systems for alerting and incident workflows.
    """

    event_id: str = Field(
        ...,
        description="Unique event identifier.",
        examples=["evt-6002"],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID from the original request.",
        examples=["evt-001"],
    )
    event_type: str = Field(
        default="ai.generation.failed",
        description="Event type discriminator.",
    )
    schema_version: str = Field(
        default="1.0",
        description="Schema version for forward compatibility.",
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp of the failure.",
    )
    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    operation: str = Field(
        ...,
        description="The generation operation that failed: chat_completion, summary_generation, or proactive_message.",
        examples=["chat_completion"],
    )
    error_code: str = Field(
        ...,
        description="Machine-readable error code.",
        examples=["PROVIDER_TIMEOUT"],
    )
    retryable: bool = Field(
        ...,
        description="Whether the failure is retryable.",
    )
    fallback_attempted: bool = Field(
        ...,
        description="Whether a fallback provider was attempted before failure.",
    )


class GenerationCompletedEvent(BaseModel):
    """
    Published to topic: ai.generation.completed

    Emitted for telemetry, monitoring, and audit trails only.
    This is NOT a second business response path.
    """

    event_id: str = Field(
        ...,
        description="Unique event identifier.",
        examples=["evt-6003"],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID from the original request.",
        examples=["evt-022"],
    )
    event_type: str = Field(
        default="ai.generation.completed",
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
    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    operation: str = Field(
        ...,
        description="The generation operation: chat_completion, summary_generation, or proactive_message.",
        examples=["summary_generation"],
    )
    model: str = Field(
        ...,
        description="Model identifier used.",
        examples=["claude-sonnet"],
    )
    usage: Optional[dict] = Field(
        None,
        description="Token usage statistics: {input_tokens, output_tokens}.",
    )
