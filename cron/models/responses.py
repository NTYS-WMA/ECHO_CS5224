"""
Response models for the Cron Service v3.0.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScheduleEntryResponse(BaseModel):
    """Response for a single schedule entry."""

    name: str = Field(..., description="Schedule name.")
    cron_expression: Optional[str] = Field(None, description="Cron expression.")
    interval_seconds: Optional[int] = Field(None, description="Interval in seconds.")
    topic: str = Field(..., description="Event topic.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Static payload.")
    enabled: bool = Field(..., description="Whether the schedule is active.")
    next_fire_at: Optional[datetime] = Field(None, description="Next fire time (UTC).")
    last_fired_at: Optional[datetime] = Field(None, description="Last fire time (UTC).")


class ScheduleListResponse(BaseModel):
    """Response for GET /api/v1/schedules."""

    schedules: List[ScheduleEntryResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of schedules.")


class SchedulerStatusResponse(BaseModel):
    """Response for GET /api/v1/scheduler/status."""

    running: bool = Field(..., description="Whether the scheduler is running.")
    tick_interval_seconds: int = Field(..., description="Tick interval in seconds.")
    total_schedules: int = Field(default=0, description="Total configured schedules.")
    active_schedules: int = Field(default=0, description="Number of enabled schedules.")
    last_tick_at: Optional[datetime] = Field(None, description="Last tick time.")


class ManualTriggerResponse(BaseModel):
    """Response for POST /api/v1/scheduler/trigger."""

    schedule_name: str = Field(..., description="Schedule that was triggered.")
    topic: str = Field(..., description="Topic the event was published to.")
    published: bool = Field(..., description="Whether the event was published.")
    error: Optional[str] = Field(None, description="Error message if failed.")
