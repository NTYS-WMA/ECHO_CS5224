"""
Event models for the Cron Service v3.0.

Defines the event envelope published to the Internal Messaging Layer
when a schedule fires.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CronTriggeredEvent(BaseModel):
    """
    Event published when a schedule fires.

    The topic is determined by the schedule entry configuration.
    The payload combines the static schedule payload with trigger
    metadata added by the scheduler.
    """

    event_id: str = Field(..., description="Unique event identifier.")
    event_type: str = Field(
        ...,
        description="Event type — matches the schedule's topic.",
    )
    source: str = Field(
        default="cron-service",
        description="Source service identifier.",
    )
    schema_version: str = Field(default="3.0", description="Schema version.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC).",
    )
    schedule_name: str = Field(
        ...,
        description="Name of the schedule that triggered this event.",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event payload from the schedule configuration.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for tracing.",
    )
