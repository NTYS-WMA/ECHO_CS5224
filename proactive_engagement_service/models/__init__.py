"""
Data models for the Proactive Engagement Service v2.0.

Exports domain entities, request/response models, and event payloads.
"""

from .domain import (
    ScheduleConfig,
    ScheduledTask,
    TaskPayload,
    TaskStatus,
    TaskType,
)
from .events import (
    OutboundMessagePayload,
    TaskDispatchedEvent,
    TaskFailedEvent,
)
from .requests import (
    ListTasksParams,
    ManualPollTriggerRequest,
    RegisterTaskRequest,
    UpdateTaskRequest,
)
from .responses import (
    PollCycleResponse,
    PollExecutionResult,
    SchedulerStatusResponse,
    TaskDeletedResponse,
    TaskListResponse,
    TaskResponse,
)

__all__ = [
    # Domain
    "ScheduleConfig",
    "ScheduledTask",
    "TaskPayload",
    "TaskStatus",
    "TaskType",
    # Events
    "OutboundMessagePayload",
    "TaskDispatchedEvent",
    "TaskFailedEvent",
    # Requests
    "ListTasksParams",
    "ManualPollTriggerRequest",
    "RegisterTaskRequest",
    "UpdateTaskRequest",
    # Responses
    "PollCycleResponse",
    "PollExecutionResult",
    "SchedulerStatusResponse",
    "TaskDeletedResponse",
    "TaskListResponse",
    "TaskResponse",
]
