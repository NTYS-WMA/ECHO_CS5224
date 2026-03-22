"""
Request models for the Proactive Engagement Service v2.0.

Includes request bodies for task registration, update, listing,
and scheduler control endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .domain import ScheduleConfig, TaskPayload, TaskType


# ------------------------------------------------------------------ #
# Task CRUD Requests
# ------------------------------------------------------------------ #


class RegisterTaskRequest(BaseModel):
    """
    Request body for POST /api/v1/tasks — Register a new scheduled task.

    The caller (service registrant) provides the target, payload, and
    schedule configuration. The Proactive Engagement Service computes
    next_run_at and persists the task via the Database Service.
    """

    owner_service: str = Field(
        ...,
        description="Name of the service registering this task.",
        examples=["conversation-orchestrator", "relationship-service"],
    )
    task_type: TaskType = Field(
        ...,
        description="Type of task: one_time or recurring.",
    )
    channel: str = Field(
        ...,
        description="Target delivery channel.",
        examples=["telegram", "whatsapp", "web"],
    )
    user_id: str = Field(
        ...,
        description="Target user identifier.",
        examples=["usr_9f2a7c41"],
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Target conversation ID. If omitted, derived from channel + user_id.",
    )
    payload: TaskPayload = Field(
        ...,
        description="Message payload to dispatch when the task fires.",
    )
    schedule_config: ScheduleConfig = Field(
        ...,
        description="Schedule configuration (when to fire).",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts on dispatch failure.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Arbitrary metadata from the registrant.",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Task expiration time (UTC). Expired tasks are auto-cancelled.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
    )


class UpdateTaskRequest(BaseModel):
    """
    Request body for PUT /api/v1/tasks/{task_id} — Update a task.

    Only provided fields are updated; omitted fields remain unchanged.
    """

    payload: Optional[TaskPayload] = Field(
        None,
        description="Updated message payload.",
    )
    schedule_config: Optional[ScheduleConfig] = Field(
        None,
        description="Updated schedule configuration.",
    )
    max_retries: Optional[int] = Field(
        None,
        ge=0,
        le=10,
        description="Updated maximum retry attempts.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata.",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Updated expiration time.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
    )


class ListTasksParams(BaseModel):
    """Query parameters for GET /api/v1/tasks — List tasks with filters."""

    owner_service: Optional[str] = Field(
        None,
        description="Filter by registrant service name.",
    )
    status: Optional[str] = Field(
        None,
        description="Filter by task status.",
    )
    user_id: Optional[str] = Field(
        None,
        description="Filter by target user ID.",
    )
    channel: Optional[str] = Field(
        None,
        description="Filter by target channel.",
    )
    task_type: Optional[str] = Field(
        None,
        description="Filter by task type (one_time / recurring).",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of tasks to return.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset for pagination.",
    )


# ------------------------------------------------------------------ #
# Scheduler Control Requests
# ------------------------------------------------------------------ #


class ManualPollTriggerRequest(BaseModel):
    """
    Request body for POST /api/v1/scheduler/trigger — Manual poll trigger.

    Used for testing and operational purposes.
    """

    max_tasks: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of due tasks to process in this poll cycle.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
    )
