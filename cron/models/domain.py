"""
Domain models for the Cron Service v4.0.

Defines the ScheduledEvent entity — a database-backed event that can be
one-time or recurring, registered by any external service.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ScheduledEvent(BaseModel):
    """
    A scheduled event stored in the database.

    Represents either a one-time or recurring event registered by an
    external service via the event registration API.
    """

    id: str = Field(..., description="UUID of the scheduled event.")
    event_name: str = Field(..., description="Human-readable event name.")
    event_type: str = Field(
        "one_time",
        description="'one_time' or 'recurring'.",
    )

    # Caller identity
    caller_service: str = Field(
        ..., description="Service that registered this event."
    )
    callback_url: Optional[str] = Field(
        None, description="HTTP callback URL for delivery."
    )
    topic: Optional[str] = Field(
        None, description="Event broker topic for delivery."
    )

    # Schedule definition
    cron_expression: Optional[str] = Field(
        None, description="5-field cron expression for recurring events."
    )
    interval_seconds: Optional[int] = Field(
        None, ge=10, description="Fixed interval in seconds."
    )
    scheduled_at: Optional[datetime] = Field(
        None, description="Exact fire time for one-time events."
    )

    # Flexible payload — each caller puts whatever context it needs
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom JSON payload attached to the event.",
    )

    # Lifecycle
    status: str = Field(
        default="active",
        description="active | paused | completed | cancelled | failed",
    )
    next_fire_at: Optional[datetime] = Field(
        None, description="Next computed fire time (UTC)."
    )
    last_fired_at: Optional[datetime] = Field(
        None, description="Last time this event fired (UTC)."
    )
    fire_count: int = Field(default=0, description="Number of times fired.")
    max_fires: Optional[int] = Field(
        None, description="Max fires (NULL=unlimited for recurring)."
    )

    # Tracing and grouping
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for distributed tracing."
    )
    group_key: Optional[str] = Field(
        None,
        description="Caller-defined grouping key (e.g. user_id).",
    )

    # Timestamps
    created_at: Optional[datetime] = Field(None, description="Created time.")
    updated_at: Optional[datetime] = Field(None, description="Last updated time.")


# Keep backward-compatible alias for internal config-based schedules
class ScheduleEntry(BaseModel):
    """Legacy in-memory schedule entry (for built-in default schedules)."""

    name: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = Field(None, ge=60)
    topic: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    next_fire_at: Optional[datetime] = None
    last_fired_at: Optional[datetime] = None
