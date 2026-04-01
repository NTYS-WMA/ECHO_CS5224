"""
Event models for the Cron Service v4.0.

Defines the event envelope published to the Internal Messaging Layer
or delivered via HTTP callback when a scheduled event fires.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CronTriggeredEvent(BaseModel):
    """
    Event published when a scheduled event fires.

    Contains all context the downstream consumer needs, including the
    caller-defined custom payload.
    """

    event_id: str = Field(..., description="Unique event identifier.")
    event_type: str = Field(
        ..., description="Event type — matches the topic or event_name."
    )
    source: str = Field(
        default="cron-service", description="Source service identifier."
    )
    schema_version: str = Field(default="4.0", description="Schema version.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC).",
    )

    # From the scheduled event
    scheduled_event_id: str = Field(
        ..., description="UUID of the scheduled_events row."
    )
    event_name: str = Field(
        ..., description="Name of the scheduled event."
    )
    caller_service: str = Field(
        ..., description="Service that registered the event."
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom payload from the registered event.",
    )

    # Legacy field for backward compatibility
    schedule_name: Optional[str] = Field(
        None, description="Deprecated — use event_name."
    )
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for tracing."
    )
    group_key: Optional[str] = Field(
        None, description="Caller-defined grouping key."
    )
