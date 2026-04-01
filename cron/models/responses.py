"""
Response models for the Cron Service v4.0.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScheduledEventResponse(BaseModel):
    """Response for a single scheduled event."""

    id: str = Field(..., description="Event UUID.")
    event_name: str = Field(..., description="Event name.")
    event_type: str = Field(..., description="one_time or recurring.")
    caller_service: str = Field(..., description="Registering service.")
    callback_url: Optional[str] = None
    topic: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(..., description="active|paused|completed|cancelled|failed")
    next_fire_at: Optional[datetime] = None
    last_fired_at: Optional[datetime] = None
    fire_count: int = 0
    max_fires: Optional[int] = None
    correlation_id: Optional[str] = None
    group_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EventListResponse(BaseModel):
    """Response for GET /api/v1/events."""

    events: List[ScheduledEventResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total matching events.")
    limit: int = 100
    offset: int = 0


class SchedulerStatusResponse(BaseModel):
    """Response for GET /api/v1/scheduler/status."""

    running: bool = Field(..., description="Whether the scheduler is running.")
    tick_interval_seconds: int = Field(..., description="Tick interval in seconds.")
    total_events_polled: int = Field(default=0, description="Total events polled since start.")
    total_events_fired: int = Field(default=0, description="Total events fired since start.")
    last_tick_at: Optional[datetime] = Field(None, description="Last tick time.")
    db_manager_url: str = Field(..., description="DB Manager URL.")


class ManualTriggerResponse(BaseModel):
    """Response for POST /api/v1/events/{event_id}/trigger."""

    event_id: str = Field(..., description="Event that was triggered.")
    event_name: str = Field(..., description="Event name.")
    topic: Optional[str] = None
    callback_url: Optional[str] = None
    published: bool = Field(..., description="Whether the event was dispatched.")
    error: Optional[str] = Field(None, description="Error message if failed.")


class RegisterEventResponse(BaseModel):
    """Response for POST /api/v1/events — event registration confirmation."""

    id: str = Field(..., description="UUID of the newly created event.")
    event_name: str
    event_type: str
    status: str
    next_fire_at: Optional[datetime] = None
    message: str = "Event registered successfully."
