"""
Domain models for the Cron Service v3.0.

Defines the ScheduleEntry entity that represents a single cron tab —
a pairing of a time expression with an event topic.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ScheduleEntry(BaseModel):
    """
    A single schedule entry (cron tab).

    Pairs a time trigger (cron expression or interval) with an event
    topic to publish when the schedule fires.
    """

    name: str = Field(
        ...,
        description="Unique schedule name (e.g. 'relationship-decay').",
    )
    cron_expression: Optional[str] = Field(
        None,
        description="5-field cron expression (e.g. '0 3 * * *').",
    )
    interval_seconds: Optional[int] = Field(
        None,
        ge=60,
        description="Fixed interval in seconds (min 60).",
    )
    topic: str = Field(
        ...,
        description="Event topic to publish when schedule fires.",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Static payload to include in the published event.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this schedule is active.",
    )
    next_fire_at: Optional[datetime] = Field(
        None,
        description="Next computed fire time (UTC). Set by the scheduler.",
    )
    last_fired_at: Optional[datetime] = Field(
        None,
        description="Last time this schedule fired (UTC).",
    )
