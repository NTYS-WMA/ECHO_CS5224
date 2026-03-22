"""
Services module for the Proactive Engagement Service v2.0.

Exports the core service components:
- DatabaseServiceClient: HTTP client for the Database Service.
- MessageDispatchClient: HTTP client for the Message Dispatch Hub.
- TaskService: Business logic for task CRUD.
- TaskExecutor: Single task execution pipeline.
- PollingScheduler: Background polling engine.
"""

from .db_client import DatabaseServiceClient
from .dispatcher import MessageDispatchClient
from .scheduler import PollingScheduler
from .task_executor import TaskExecutor
from .task_service import TaskService

__all__ = [
    "DatabaseServiceClient",
    "MessageDispatchClient",
    "PollingScheduler",
    "TaskExecutor",
    "TaskService",
]
