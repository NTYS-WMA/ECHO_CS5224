"""
Request models for the Cron Service v4.0.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RegisterEventRequest(BaseModel):
    """Request body for POST /api/v1/events — register a new scheduled event."""

    event_name: str = Field(
        ..., description="Human-readable event name (e.g. 'proactive-reminder-user123')."
    )
    event_type: str = Field(
        default="one_time",
        description="'one_time' or 'recurring'.",
    )
    caller_service: str = Field(
        ..., description="Service identity registering this event."
    )

    # Delivery target — at least one should be provided
    callback_url: Optional[str] = Field(
        None, description="HTTP callback URL to POST when event fires."
    )
    topic: Optional[str] = Field(
        None, description="Event broker topic to publish to."
    )

    # Schedule definition
    cron_expression: Optional[str] = Field(
        None, description="5-field cron expression (for recurring)."
    )
    interval_seconds: Optional[int] = Field(
        None, ge=10, description="Fixed interval in seconds (for recurring)."
    )
    scheduled_at: Optional[datetime] = Field(
        None, description="Exact UTC time to fire (for one_time)."
    )

    # Custom payload — this is where callers put their specific data
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Custom JSON payload delivered with the event. "
            "E.g. {\"user_id\": \"u123\", \"conversation_id\": \"c456\", "
            "\"message_template\": \"follow_up\"}."
        ),
    )

    max_fires: Optional[int] = Field(
        None,
        description="Maximum number of times to fire (NULL=unlimited for recurring).",
    )
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for distributed tracing."
    )
    group_key: Optional[str] = Field(
        None,
        description=(
            "Caller-defined grouping key for batch operations. "
            "E.g. user_id to cancel all events for a user."
        ),
    )


class UpdateEventRequest(BaseModel):
    """Request body for PUT /api/v1/events/{event_id}."""

    event_name: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = Field(None, ge=10)
    scheduled_at: Optional[datetime] = None
    payload: Optional[Dict[str, Any]] = None
    max_fires: Optional[int] = None
    correlation_id: Optional[str] = None
    group_key: Optional[str] = None


class ManualTriggerRequest(BaseModel):
    """Request body for POST /api/v1/events/{event_id}/trigger."""

    payload_override: Optional[Dict[str, Any]] = Field(
        None, description="Override the event's payload for this trigger."
    )
