"""
Response models for the Proactive Engagement Service v2.0.

Includes response bodies for task CRUD operations, scheduler status,
and poll execution results.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .domain import ScheduleConfig, ScheduledTask, TaskPayload, TaskStatus, TaskType


# ------------------------------------------------------------------ #
# Task CRUD Responses
# ------------------------------------------------------------------ #


class TaskResponse(BaseModel):
    """Response for a single task (GET, POST, PUT)."""

    task_id: str = Field(..., description="Unique task identifier.")
    owner_service: str = Field(..., description="Registrant service name.")
    task_type: TaskType = Field(..., description="Task type.")
    status: TaskStatus = Field(..., description="Current task status.")
    channel: str = Field(..., description="Target delivery channel.")
    user_id: str = Field(..., description="Target user identifier.")
    conversation_id: Optional[str] = Field(None, description="Target conversation ID.")
    payload: TaskPayload = Field(..., description="Message payload.")
    schedule_config: ScheduleConfig = Field(..., description="Schedule configuration.")
    next_run_at: Optional[datetime] = Field(None, description="Next execution time (UTC).")
    last_run_at: Optional[datetime] = Field(None, description="Last execution time (UTC).")
    retry_count: int = Field(default=0, description="Current retry count.")
    max_retries: int = Field(default=3, description="Maximum retry attempts.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Registrant metadata.")
    created_at: datetime = Field(..., description="Creation timestamp (UTC).")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC).")
    expires_at: Optional[datetime] = Field(None, description="Expiration time (UTC).")

    @classmethod
    def from_domain(cls, task: ScheduledTask) -> "TaskResponse":
        """Create a TaskResponse from a ScheduledTask domain model."""
        return cls(**task.model_dump())


class TaskListResponse(BaseModel):
    """Response for GET /api/v1/tasks — paginated task list."""

    tasks: List[TaskResponse] = Field(
        default_factory=list,
        description="List of tasks matching the query.",
    )
    total: int = Field(
        ...,
        description="Total number of tasks matching the filters (for pagination).",
    )
    limit: int = Field(..., description="Requested page size.")
    offset: int = Field(..., description="Requested offset.")


class TaskDeletedResponse(BaseModel):
    """Response for DELETE /api/v1/tasks/{task_id}."""

    task_id: str = Field(..., description="Deleted task identifier.")
    status: str = Field(
        default="cancelled",
        description="Final task status after deletion.",
    )
    message: str = Field(
        default="Task cancelled successfully.",
        description="Human-readable confirmation.",
    )


# ------------------------------------------------------------------ #
# Scheduler Responses
# ------------------------------------------------------------------ #


class SchedulerStatusResponse(BaseModel):
    """Response for GET /api/v1/scheduler/status."""

    running: bool = Field(
        ...,
        description="Whether the polling engine is currently running.",
    )
    poll_interval_seconds: int = Field(
        ...,
        description="Configured polling interval in seconds.",
    )
    last_poll_at: Optional[datetime] = Field(
        None,
        description="Timestamp of the last poll cycle.",
    )
    tasks_pending: int = Field(
        default=0,
        description="Number of tasks in 'scheduled' status.",
    )
    tasks_executing: int = Field(
        default=0,
        description="Number of tasks currently executing.",
    )


class PollExecutionResult(BaseModel):
    """Result of a single task execution within a poll cycle."""

    task_id: str = Field(..., description="Task identifier.")
    success: bool = Field(..., description="Whether dispatch succeeded.")
    error: Optional[str] = Field(None, description="Error message if failed.")


class PollCycleResponse(BaseModel):
    """Response for POST /api/v1/scheduler/trigger — manual poll result."""

    poll_id: str = Field(..., description="Unique poll cycle identifier.")
    tasks_found: int = Field(..., description="Number of due tasks found.")
    tasks_dispatched: int = Field(..., description="Number of tasks successfully dispatched.")
    tasks_failed: int = Field(..., description="Number of tasks that failed dispatch.")
    results: List[PollExecutionResult] = Field(
        default_factory=list,
        description="Per-task execution results.",
    )
    duration_ms: float = Field(..., description="Poll cycle duration in milliseconds.")
