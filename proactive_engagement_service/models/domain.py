"""
Domain models for the Proactive Engagement Service.

Defines the core ScheduledTask entity, task lifecycle enums,
and related value objects used throughout the service.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Enums
# ------------------------------------------------------------------ #


class TaskType(str, Enum):
    """Type of scheduled task."""

    ONE_TIME = "one_time"
    RECURRING = "recurring"


class TaskStatus(str, Enum):
    """
    Task lifecycle status.

    Lifecycle:
        PENDING → SCHEDULED → EXECUTING → COMPLETED
                           ↘ FAILED → (retry) → SCHEDULED
                           ↘ CANCELLED
        PAUSED (manual pause/resume) ↔ SCHEDULED
    """

    PENDING = "pending"
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


# ------------------------------------------------------------------ #
# Value Objects
# ------------------------------------------------------------------ #


class ScheduleConfig(BaseModel):
    """
    Schedule configuration for a task.

    For one_time tasks, only `scheduled_at` is required.
    For recurring tasks, provide `cron_expression` or `interval_seconds`.
    """

    scheduled_at: Optional[datetime] = Field(
        None,
        description="Specific datetime for one-time execution (UTC).",
    )
    cron_expression: Optional[str] = Field(
        None,
        description="Cron expression for recurring tasks (5-field standard).",
        examples=["0 9 * * *"],
    )
    interval_seconds: Optional[int] = Field(
        None,
        ge=60,
        description="Fixed interval in seconds for recurring tasks (min 60s).",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for schedule interpretation (IANA format).",
        examples=["Asia/Singapore", "UTC"],
    )


class TaskPayload(BaseModel):
    """
    Message payload to be dispatched when the task fires.

    The payload is opaque to the Proactive Engagement Service — it is
    assembled by the service registrant and forwarded as-is to the
    Message Dispatch Hub.
    """

    message_type: str = Field(
        default="text",
        description="Type of message: text, template, rich.",
        examples=["text", "template", "rich"],
    )
    content: Optional[str] = Field(
        None,
        description="Direct text content (for message_type='text').",
    )
    template_id: Optional[str] = Field(
        None,
        description="AI Generation Service template ID (for message_type='template').",
    )
    template_variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Variables for template rendering.",
    )
    attachments: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Optional attachments (images, files, etc.).",
    )
    extra: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional payload fields defined by the registrant.",
    )


# ------------------------------------------------------------------ #
# Core Entity
# ------------------------------------------------------------------ #


class ScheduledTask(BaseModel):
    """
    Core domain entity representing a scheduled proactive message task.

    Registered by service callers, persisted in the database, and
    polled by the internal scheduler for execution.
    """

    task_id: str = Field(
        ...,
        description="Unique task identifier.",
        examples=["task_a1b2c3d4e5"],
    )
    owner_service: str = Field(
        ...,
        description="Name of the service that registered this task.",
        examples=["conversation-orchestrator", "relationship-service"],
    )
    task_type: TaskType = Field(
        ...,
        description="Type of task: one_time or recurring.",
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current task status.",
    )

    # Target
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
        description="Target conversation ID (derived if not provided).",
    )

    # Payload
    payload: TaskPayload = Field(
        ...,
        description="Message payload to dispatch.",
    )

    # Schedule
    schedule_config: ScheduleConfig = Field(
        ...,
        description="Schedule configuration.",
    )
    next_run_at: Optional[datetime] = Field(
        None,
        description="Next scheduled execution time (UTC, indexed for polling).",
    )
    last_run_at: Optional[datetime] = Field(
        None,
        description="Last execution time (UTC).",
    )

    # Retry
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Current retry count.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts before marking as failed.",
    )

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Arbitrary metadata from the registrant.",
    )
    created_at: datetime = Field(
        ...,
        description="Task creation timestamp (UTC).",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp (UTC).",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Task expiration time (UTC). Expired tasks are auto-cancelled.",
    )
